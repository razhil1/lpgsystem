from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app.models import Transaction, TransactionItem, Tank, TankHistory, Consumer, Plant, Payment, AuditLog
from app.extensions import db
from datetime import datetime, date
from app.utils.settings import get_setting

transactions_bp = Blueprint('transactions', __name__)


def parse_date(value):
    """Convert a date string 'YYYY-MM-DD' from an HTML form input into a
    Python date object. SQLite requires real date objects, not strings.
    Returns None if the value is empty or cannot be parsed."""
    if not value:
        return None
    try:
        return datetime.strptime(value, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        return None


def generate_invoice(default_prefix='INV'):
    prefix = get_setting('Invoice Prefix', default=default_prefix)
    depth = int(get_setting('Invoice Number Depth', default='5'))
    
    last = Transaction.query.order_by(Transaction.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    
    # Format: PREFIX-YYYYMMDD-00001
    date_str = date.today().strftime("%Y%m%d")
    return f'{prefix}-{date_str}-{next_id:0{depth}d}'


# ─────────────────────────────────────────
# LIST
# ─────────────────────────────────────────
@transactions_bp.route('/')
@login_required
def index():
    t_type = request.args.get('type', '')
    date_from = request.args.get('date_from', '')
    date_to = request.args.get('date_to', '')
    page = request.args.get('page', 1, type=int)

    q = Transaction.query
    if t_type:
        q = q.filter(Transaction.transaction_type == t_type)
    if date_from:
        q = q.filter(Transaction.transaction_date >= parse_date(date_from))
    if date_to:
        q = q.filter(Transaction.transaction_date <= parse_date(date_to))

    transactions = q.order_by(Transaction.created_at.desc()).paginate(page=page, per_page=20)
    return render_template('transactions/index.html',
                           transactions=transactions,
                           t_type=t_type, date_from=date_from, date_to=date_to)


# ─────────────────────────────────────────
# DELIVERY (OUT to Consumer)
# ─────────────────────────────────────────
@transactions_bp.route('/delivery/create', methods=['GET', 'POST'])
@login_required
def create_delivery():
    consumers = Consumer.query.filter_by(is_active=True).order_by(Consumer.business_name).all()
    SIZES = get_setting('Tank Sizes', is_list=True)
    CATEGORIES = get_setting('Tank Categories', is_list=True)
    WAREHOUSE = get_setting('Warehouse Location Name', default='Warehouse')

    # Stock available in warehouse (Full)
    stock = {}
    for s in SIZES:
        stock[s] = {}
        for cat in CATEGORIES:
            stock[s][cat] = Tank.query.filter_by(
                tank_size=s, tank_category=cat, status='Full', location=WAREHOUSE, is_active=True
            ).count()

    if request.method == 'POST':
        consumer_id = request.form.get('consumer_id')
        consumer_id = int(consumer_id) if consumer_id else None
        txn_date = parse_date(request.form.get('transaction_date')) or date.today()
        consumer = db.session.get(Consumer, consumer_id) if consumer_id else None

        # Collect per-size quantities and prices
        items_data = []
        for s in SIZES:
            sid = s.replace(' ', '_')
            for cat in CATEGORIES:
                cid = cat.replace(' ', '_').lower()
                qty_raw = request.form.get(f'qty_{cid}_{sid}', '0').strip() or '0'
                price_raw = request.form.get(f'price_{sid}', '0').strip() or '0'
                try:
                    qty = int(float(qty_raw))
                    price = float(price_raw)
                except ValueError:
                    qty = 0
                    price = 0.0
                
                if qty > 0:
                    items_data.append({'size': s, 'category': cat, 'qty': qty, 'price': price})

        if not items_data:
            flash('Please enter at least 1 tank to deliver.', 'danger')
            return render_template('transactions/delivery_form.html',
                                   consumers=consumers, stock=stock)

        # Validate stock availability
        for item in items_data:
            avail = Tank.query.filter_by(
                tank_size=item['size'], tank_category=item['category'], status='Full',
                location=WAREHOUSE, is_active=True
            ).count()
            if item['qty'] > avail:
                flash(f"Not enough {item['size']} ({item['category']}) full tanks. Available: {avail}, Requested: {item['qty']}", 'danger')
                return render_template('transactions/delivery_form.html',
                                       consumers=consumers, stock=stock)

        # Create transaction
        txn = Transaction(
            invoice_no=generate_invoice('DLV'),
            transaction_type='Delivery',
            transaction_date=txn_date,
            consumer_id=consumer_id,
            driver_name=request.form.get('driver_name'),
            truck_plate=request.form.get('truck_plate'),
            payment_status=request.form.get('payment_status', 'Unpaid'),
            remarks=request.form.get('remarks'),
            created_by=current_user.id
        )
        db.session.add(txn)
        db.session.flush()

        grand_total = 0

        for item_data in items_data:
            size = item_data['size']
            qty = item_data['qty']
            price = item_data['price']
            subtotal = qty * price
            grand_total += subtotal

            # Get tanks FIFO (oldest first) for this size
            tanks_to_deliver = Tank.query.filter_by(
                tank_size=size, tank_category=item_data['category'], status='Full',
                location=WAREHOUSE, is_active=True
            ).order_by(Tank.id.asc()).limit(qty).all()

            for tank in tanks_to_deliver:
                prev_location = tank.location
                tank.location = 'With Consumer'
                tank.status = 'Full'
                tank.current_consumer_id = consumer_id
                tank.last_transaction_date = datetime.utcnow()

                ti = TransactionItem(
                    transaction_id=txn.id,
                    tank_id=tank.id,
                    tank_size=size,
                    tank_category=item_data['category'],
                    quantity=1,
                    unit_price=price
                )
                db.session.add(ti)

                history = TankHistory(
                    tank_id=tank.id,
                    transaction_id=txn.id,
                    event_type='Delivered',
                    event_description=f'Delivered to {consumer.business_name if consumer else "Consumer"} ({size})',
                    from_location=prev_location,
                    to_location='With Consumer',
                    consumer_id=consumer_id,
                    created_by=current_user.id
                )
                db.session.add(history)

            # If fewer real tanks than qty (shouldn't happen after validation, but safety net):
            # create a quantity-only item for the remainder
            real_count = len(tanks_to_deliver)
            if real_count < qty:
                remainder = qty - real_count
                ti_bulk = TransactionItem(
                    transaction_id=txn.id,
                    tank_id=None,
                    tank_size=size,
                    tank_category=item_data['category'],
                    quantity=remainder,
                    unit_price=price
                )
                db.session.add(ti_bulk)

        txn.total_amount = grand_total

        # Handle payment
        amount_paid = float(request.form.get('amount_paid', 0) or 0)
        if amount_paid > 0:
            pay = Payment(
                transaction_id=txn.id,
                payment_date=date.today(),
                amount=amount_paid,
                payment_method=request.form.get('payment_method', 'Cash'),
                created_by=current_user.id
            )
            db.session.add(pay)
            txn.amount_paid = amount_paid
            if amount_paid >= grand_total:
                txn.payment_status = 'Paid'
            else:
                txn.payment_status = 'Partial'

        if consumer:
            consumer.outstanding_balance = float(consumer.outstanding_balance or 0) + (grand_total - amount_paid)

        log = AuditLog(user_id=current_user.id, action='CREATE', module='transactions',
                       record_id=txn.id,
                       description=f'Created delivery {txn.invoice_no} — {sum(i["qty"] for i in items_data)} tanks',
                       ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash(f'Delivery {txn.invoice_no} created successfully!', 'success')
        return redirect(url_for('transactions.view', id=txn.id))

    return render_template('transactions/delivery_form.html',
                           consumers=consumers, stock=stock)



# ─────────────────────────────────────────
# RETURN (IN from Consumer)
# ─────────────────────────────────────────
@transactions_bp.route('/return/create', methods=['GET', 'POST'])
@login_required
def create_return():
    consumers = Consumer.query.filter_by(is_active=True).order_by(Consumer.business_name).all()
    SIZES = get_setting('Tank Sizes', is_list=True)
    CATEGORIES = get_setting('Tank Categories', is_list=True)
    WAREHOUSE = get_setting('Warehouse Location Name', default='Warehouse')

    if request.method == 'POST':
        consumer_id = request.form.get('consumer_id')
        consumer_id = int(consumer_id) if consumer_id else None
        consumer = db.session.get(Consumer, consumer_id) if consumer_id else None

        # Collect per-size returns
        items_data = []
        for s in SIZES:
            sid = s.replace(' ', '_')
            for cat in CATEGORIES:
                cid = cat.replace(' ', '_').lower()
                qty_raw = request.form.get(f'qty_{cid}_{sid}', '0').strip() or '0'
                try:
                    qty = int(float(qty_raw))
                except ValueError:
                    qty = 0
                cond = request.form.get(f'condition_{cid}_{sid}', 'Good')
                if qty > 0:
                    items_data.append({'size': s, 'category': cat, 'qty': qty, 'condition': cond})

        if not items_data:
            flash('Please enter at least 1 tank to return.', 'danger')
            return render_template('transactions/return_form.html', consumers=consumers)

        txn = Transaction(
            invoice_no=generate_invoice('RTN'),
            transaction_type='Return',
            transaction_date=parse_date(request.form.get('transaction_date')) or date.today(),
            consumer_id=consumer_id,
            remarks=request.form.get('remarks'),
            created_by=current_user.id,
            payment_status='Paid',
            total_amount=0
        )
        db.session.add(txn)
        db.session.flush()

        total_returned = 0
        for item_data in items_data:
            size = item_data['size']
            qty = item_data['qty']
            condition = item_data['condition']

            # Pick tanks for this consumer + size (FIFO)
            tanks_to_return = Tank.query.filter_by(
                tank_size=size,
                tank_category=item_data['category'],
                location='With Consumer',
                current_consumer_id=consumer_id,
                is_active=True
            ).order_by(Tank.id.asc()).limit(qty).all()

            for tank in tanks_to_return:
                tank.location = WAREHOUSE
                tank.status = 'Empty' if condition == 'Good' else 'For Refill'
                tank.current_consumer_id = None
                tank.last_transaction_date = datetime.utcnow()

                ti = TransactionItem(
                    transaction_id=txn.id,
                    tank_id=tank.id,
                    tank_size=size,
                    tank_category=item_data['category'],
                    quantity=1,
                    condition=condition
                )
                db.session.add(ti)

                history = TankHistory(
                    tank_id=tank.id,
                    transaction_id=txn.id,
                    event_type='Returned',
                    event_description=f'Returned from {consumer.business_name if consumer else "Consumer"} | {size} | {condition}',
                    from_location='With Consumer',
                    to_location=WAREHOUSE,
                    consumer_id=consumer_id,
                    created_by=current_user.id
                )
                db.session.add(history)
                total_returned += 1

            # If fewer tanks found than entered (create bulk item for remainder)
            if len(tanks_to_return) < qty:
                remainder = qty - len(tanks_to_return)
                ti_bulk = TransactionItem(
                    transaction_id=txn.id,
                    tank_id=None,
                    tank_size=size,
                    tank_category=item_data['category'],
                    quantity=remainder,
                    condition=condition
                )
                db.session.add(ti_bulk)
                total_returned += remainder

        log = AuditLog(user_id=current_user.id, action='CREATE', module='transactions',
                       record_id=txn.id,
                       description=f'Return {txn.invoice_no} — {total_returned} tanks from {consumer.business_name if consumer else "?"}',
                       ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash(f'Return {txn.invoice_no} recorded. {total_returned} tanks received.', 'success')
        return redirect(url_for('transactions.view', id=txn.id))

    return render_template('transactions/return_form.html', consumers=consumers)



# ─────────────────────────────────────────
# PLANT OUT (Send empties to plant)
# ─────────────────────────────────────────
@transactions_bp.route('/plant-out/create', methods=['GET', 'POST'])
@login_required
def create_plant_out():
    plants = Plant.query.filter_by(is_active=True).all()
    empty_tanks = Tank.query.filter_by(
        location='Warehouse', status='Empty', is_active=True
    ).order_by(Tank.serial_number).all()

    if request.method == 'POST':
        plant_id = request.form.get('plant_id')
        plant_id = int(plant_id) if plant_id else None
        tank_ids = request.form.getlist('tank_ids')

        if not tank_ids:
            flash('Please select at least one tank.', 'danger')
            return render_template('transactions/plant_out_form.html',
                                   plants=plants, tanks=empty_tanks)

        plant = db.session.get(Plant, plant_id) if plant_id else None
        txn = Transaction(
            invoice_no=generate_invoice('PLO'),
            transaction_type='Plant OUT',
            transaction_date=parse_date(request.form.get('transaction_date')) or date.today(),
            plant_id=plant_id,
            remarks=request.form.get('remarks'),
            created_by=current_user.id,
            payment_status='Paid'
        )
        db.session.add(txn)
        db.session.flush()

        total_cost = 0
        for tank_id in tank_ids:
            tank = db.session.get(Tank, int(tank_id))
            if not tank:
                continue

            # Determine refill cost based on tank size
            refill_cost = 0
            if plant:
                size_map = {
                    '11kg': float(plant.refill_cost_11kg or 0),
                    '11kg Fiber': float(plant.refill_cost_11kg_fiber or 0),
                    '22kg': float(plant.refill_cost_22kg or 0),
                    '50kg': float(plant.refill_cost_50kg or 0),
                    'Industrial': float(plant.refill_cost_industrial or 0),
                }
                refill_cost = size_map.get(tank.tank_size, 0)
            total_cost += refill_cost

            item = TransactionItem(
                transaction_id=txn.id,
                tank_id=tank.id,
                refill_cost=refill_cost
            )
            db.session.add(item)

            tank.location = 'At Plant'
            tank.status = 'For Refill'
            tank.current_plant_id = plant_id
            tank.last_transaction_date = datetime.utcnow()

            history = TankHistory(
                tank_id=tank.id,
                transaction_id=txn.id,
                event_type='Sent to Plant',
                event_description=f'Sent to {plant.plant_name if plant else "Plant"} for refilling',
                from_location='Warehouse',
                to_location='At Plant',
                plant_id=plant_id,
                created_by=current_user.id
            )
            db.session.add(history)

        txn.total_amount = total_cost
        db.session.commit()
        flash(f'Plant OUT {txn.invoice_no} recorded.', 'success')
        return redirect(url_for('transactions.view', id=txn.id))

    return render_template('transactions/plant_out_form.html',
                           plants=plants, tanks=empty_tanks)


# ─────────────────────────────────────────
# PLANT IN (Receive full tanks from plant)
# ─────────────────────────────────────────
@transactions_bp.route('/plant-in/create', methods=['GET', 'POST'])
@login_required
def create_plant_in():
    plants = Plant.query.filter_by(is_active=True).all()
    # Tanks currently At Plant
    at_plant_tanks = Tank.query.filter_by(
        location='At Plant', is_active=True
    ).order_by(Tank.serial_number).all()

    if request.method == 'POST':
        plant_id = request.form.get('plant_id')
        plant_id = int(plant_id) if plant_id else None
        tank_ids = request.form.getlist('tank_ids')

        if not tank_ids:
            flash('Please select at least one tank.', 'danger')
            return render_template('transactions/plant_in_form.html',
                                   plants=plants, tanks=at_plant_tanks)

        plant = db.session.get(Plant, plant_id) if plant_id else None
        txn = Transaction(
            invoice_no=generate_invoice('PLI'),
            transaction_type='Plant IN',
            transaction_date=parse_date(request.form.get('transaction_date')) or date.today(),
            plant_id=plant_id,
            remarks=request.form.get('remarks'),
            created_by=current_user.id,
            payment_status='Paid'
        )
        db.session.add(txn)
        db.session.flush()

        for tank_id in tank_ids:
            tank = db.session.get(Tank, int(tank_id))
            if not tank:
                continue

            item = TransactionItem(transaction_id=txn.id, tank_id=tank.id)
            db.session.add(item)

            tank.location = 'Warehouse'
            tank.status = 'Full'
            tank.current_plant_id = None
            tank.last_transaction_date = datetime.utcnow()

            history = TankHistory(
                tank_id=tank.id,
                transaction_id=txn.id,
                event_type='Received from Plant',
                event_description=f'Received FULL from {plant.plant_name if plant else "Plant"}',
                from_location='At Plant',
                to_location='Warehouse',
                plant_id=plant_id,
                created_by=current_user.id
            )
            db.session.add(history)

        db.session.commit()
        flash(f'Plant IN {txn.invoice_no} recorded.', 'success')
        return redirect(url_for('transactions.view', id=txn.id))

    return render_template('transactions/plant_in_form.html',
                           plants=plants, tanks=at_plant_tanks)


# ─────────────────────────────────────────
# VIEW transaction
# ─────────────────────────────────────────
@transactions_bp.route('/<int:id>')
@login_required
def view(id):
    txn = Transaction.query.get_or_404(id)
    items = txn.items.all()
    payments = txn.payments.all()
    return render_template('transactions/view.html',
                           txn=txn, items=items, payments=payments)


# ─────────────────────────────────────────
# ADD PAYMENT
# ─────────────────────────────────────────
@transactions_bp.route('/<int:id>/add-payment', methods=['POST'])
@login_required
def add_payment(id):
    txn = Transaction.query.get_or_404(id)
    amount = float(request.form.get('amount', 0))
    if amount <= 0:
        flash('Invalid payment amount.', 'danger')
        return redirect(url_for('transactions.view', id=id))

    payment = Payment(
        transaction_id=txn.id,
        payment_date=date.today(),
        amount=amount,
        payment_method=request.form.get('payment_method', 'Cash'),
        reference_no=request.form.get('reference_no'),
        notes=request.form.get('notes'),
        created_by=current_user.id
    )
    db.session.add(payment)

    txn.amount_paid = float(txn.amount_paid or 0) + amount
    if txn.amount_paid >= float(txn.total_amount or 0):
        txn.payment_status = 'Paid'
        txn.amount_paid = float(txn.total_amount)
    else:
        txn.payment_status = 'Partial'

    # Update consumer outstanding
    if txn.consumer:
        txn.consumer.outstanding_balance = max(
            0, float(txn.consumer.outstanding_balance or 0) - amount
        )

    db.session.commit()
    flash(f'Payment of ₱{amount:,.2f} recorded.', 'success')
    return redirect(url_for('transactions.view', id=id))


# ─────────────────────────────────────────
# AJAX: Get tanks by consumer
# ─────────────────────────────────────────
@transactions_bp.route('/api/consumer-tanks/<int:consumer_id>')
@login_required
def consumer_tanks(consumer_id):
    tanks = Tank.query.filter_by(
        location='With Consumer',
        current_consumer_id=consumer_id,
        is_active=True
    ).all()
    return jsonify([{
        'id': t.id,
        'serial_number': t.serial_number,
        'tank_size': t.tank_size,
        'tank_category': t.tank_category,
        'status': t.status,
    } for t in tanks])


# ─────────────────────────────────────────
# DELETE transaction
# ─────────────────────────────────────────
@transactions_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.role != 'admin':
        flash('Permission denied.', 'danger')
        return redirect(url_for('transactions.index'))
    txn = Transaction.query.get_or_404(id)
    inv = txn.invoice_no
    db.session.delete(txn)
    log = AuditLog(user_id=current_user.id, action='DELETE', module='transactions',
                   record_id=id,
                   description=f'Deleted transaction: {inv}',
                   ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    flash(f'Transaction {inv} deleted.', 'warning')
    return redirect(url_for('transactions.index'))


# ─────────────────────────────────────────
# BATCH DELETE transactions
# ─────────────────────────────────────────
@transactions_bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Permission denied.'}), 403

    txn_ids = request.form.getlist('ids[]')
    if not txn_ids:
        return jsonify({'success': False, 'message': 'No items selected.'}), 400

    count = 0
    for tid in txn_ids:
        txn = db.session.get(Transaction, int(tid))
        if txn:
            inv = txn.invoice_no
            db.session.delete(txn)
            count += 1
            log = AuditLog(user_id=current_user.id, action='DELETE', module='transactions',
                           record_id=int(tid),
                           description=f'Deleted transaction (Batch): {inv}',
                           ip_address=request.remote_addr)
            db.session.add(log)

    db.session.commit()
    flash(f'Successfully deleted {count} transactions.', 'warning')
    return jsonify({'success': True, 'redirect': url_for('transactions.index')})
