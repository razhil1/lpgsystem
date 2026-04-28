from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app.models import Consumer, AuditLog, Tank, Transaction, TankHistory
from app.extensions import db
from sqlalchemy import func
from datetime import datetime

consumers_bp = Blueprint('consumers', __name__)


def generate_consumer_code():
    last = Consumer.query.order_by(Consumer.id.desc()).first()
    next_id = (last.id + 1) if last else 1
    return f'CON-{next_id:05d}'


# ──────────────────────────────────────────────────────
# INDEX — list with live tank counts
# ──────────────────────────────────────────────────────
@consumers_bp.route('/')
@login_required
def index():
    search = request.args.get('search', '')
    ctype  = request.args.get('type', '')
    page   = request.args.get('page', 1, type=int)

    q = Consumer.query.filter_by(is_active=True)
    if search:
        q = q.filter(Consumer.business_name.ilike(f'%{search}%'))
    if ctype:
        q = q.filter(Consumer.consumer_type == ctype)

    consumers = q.order_by(Consumer.business_name).paginate(page=page, per_page=20)

    # ── Build per-consumer tank stats in a single query (no N+1) ──
    consumer_ids = [c.id for c in consumers.items]

    rows = db.session.query(
        Tank.current_consumer_id,
        Tank.status,
        Tank.tank_size,
        func.count(Tank.id).label('cnt')
    ).filter(
        Tank.current_consumer_id.in_(consumer_ids),
        Tank.location == 'With Consumer',
        Tank.is_active == True
    ).group_by(
        Tank.current_consumer_id, Tank.status, Tank.tank_size
    ).all()

    # tank_stats[consumer_id] = {'full': int, 'empty': int, 'total': int,
    #                             'by_size': {size: {'full': int, 'empty': int}}}
    tank_stats = {}
    for row in rows:
        cid = row.current_consumer_id
        if cid not in tank_stats:
            tank_stats[cid] = {'full': 0, 'empty': 0, 'total': 0, 'by_size': {}}
        tank_stats[cid]['total'] += row.cnt
        if row.status == 'Full':
            tank_stats[cid]['full'] += row.cnt
        elif row.status == 'Empty':
            tank_stats[cid]['empty'] += row.cnt
        sz = row.tank_size
        if sz not in tank_stats[cid]['by_size']:
            tank_stats[cid]['by_size'][sz] = {'full': 0, 'empty': 0}
        if row.status == 'Full':
            tank_stats[cid]['by_size'][sz]['full'] += row.cnt
        elif row.status == 'Empty':
            tank_stats[cid]['by_size'][sz]['empty'] += row.cnt

    # Calculate Consolidated Totals for the header
    total_full_all = sum(s['full'] for s in tank_stats.values())
    total_empty_all = sum(s['empty'] for s in tank_stats.values())
    total_all_consumers = sum(s['total'] for s in tank_stats.values())

    return render_template('consumers/index.html',
                           consumers=consumers,
                           search=search,
                           ctype=ctype,
                           tank_stats=tank_stats,
                           total_full_all=total_full_all,
                           total_empty_all=total_empty_all,
                           total_all_consumers=total_all_consumers)


# ──────────────────────────────────────────────────────
# CREATE
# ──────────────────────────────────────────────────────
@consumers_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        consumer = Consumer(
            consumer_code=generate_consumer_code(),
            business_name=request.form['business_name'],
            contact_person=request.form.get('contact_person'),
            address=request.form.get('address'),
            phone=request.form.get('phone'),
            email=request.form.get('email'),
            consumer_type=request.form['consumer_type'],
            credit_limit=request.form.get('credit_limit') or 0,
            notes=request.form.get('notes'),
            created_by=current_user.id
        )
        db.session.add(consumer)
        db.session.flush()
        log = AuditLog(user_id=current_user.id, action='CREATE', module='consumers',
                       record_id=consumer.id,
                       description=f'Created consumer: {consumer.business_name}',
                       ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash(f'Consumer "{consumer.business_name}" created successfully.', 'success')
        return redirect(url_for('consumers.index'))

    return render_template('consumers/form.html', consumer=None, action='Create')


# ──────────────────────────────────────────────────────
# EDIT
# ──────────────────────────────────────────────────────
@consumers_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    consumer = Consumer.query.get_or_404(id)
    if request.method == 'POST':
        consumer.business_name  = request.form['business_name']
        consumer.contact_person = request.form.get('contact_person')
        consumer.address        = request.form.get('address')
        consumer.phone          = request.form.get('phone')
        consumer.email          = request.form.get('email')
        consumer.consumer_type  = request.form['consumer_type']
        consumer.credit_limit   = request.form.get('credit_limit') or 0
        consumer.notes          = request.form.get('notes')

        log = AuditLog(user_id=current_user.id, action='UPDATE', module='consumers',
                       record_id=consumer.id,
                       description=f'Updated consumer: {consumer.business_name}',
                       ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash('Consumer updated successfully.', 'success')
        return redirect(url_for('consumers.index'))

    return render_template('consumers/form.html', consumer=consumer, action='Edit')


# ──────────────────────────────────────────────────────
# VIEW — detail with tank inventory
# ──────────────────────────────────────────────────────
@consumers_bp.route('/<int:id>/view')
@login_required
def view(id):
    consumer = Consumer.query.get_or_404(id)

    transactions = Transaction.query.filter_by(
        consumer_id=id
    ).order_by(Transaction.created_at.desc()).limit(20).all()

    # All tanks currently at this consumer
    from app.utils.settings import get_setting
    SIZES = get_setting('Tank Sizes', is_list=True)
    CATEGORIES = get_setting('Tank Categories', is_list=True)
    tanks_here = Tank.query.filter_by(
        current_consumer_id=id,
        location='With Consumer',
        is_active=True
    ).order_by(Tank.tank_size, Tank.serial_number).all()

    # Build breakdown by size
    tank_inventory = {}
    for s in SIZES:
        size_tanks = [t for t in tanks_here if t.tank_size == s]
        tank_inventory[s] = {
            'full':  sum(1 for t in size_tanks if t.status == 'Full'),
            'empty': sum(1 for t in size_tanks if t.status == 'Empty'),
            'other': sum(1 for t in size_tanks if t.status not in ('Full', 'Empty')),
            'total': len(size_tanks),
            'tanks': size_tanks,
        }

    total_full  = sum(v['full']  for v in tank_inventory.values())
    total_empty = sum(v['empty'] for v in tank_inventory.values())
    total_tanks = sum(v['total'] for v in tank_inventory.values())

    return render_template('consumers/view.html',
                           consumer=consumer,
                           transactions=transactions,
                           tank_inventory=tank_inventory,
                           sizes=SIZES,
                           total_full=total_full,
                           total_empty=total_empty,
                           total_tanks=total_tanks)


# ──────────────────────────────────────────────────────
# UPDATE TANK STATUS — bulk Full/Empty toggle per consumer
# ──────────────────────────────────────────────────────
@consumers_bp.route('/<int:id>/update-tanks', methods=['GET', 'POST'])
@login_required
def update_tanks(id):
    consumer = Consumer.query.get_or_404(id)
    from app.utils.settings import get_setting
    SIZES = get_setting('Tank Sizes', is_list=True)

    tanks_here = Tank.query.filter_by(
        current_consumer_id=id,
        location='With Consumer',
        is_active=True
    ).order_by(Tank.tank_size, Tank.serial_number).all()

    if request.method == 'POST':
        changed = 0
        changes_desc = []

        for tank in tanks_here:
            new_status = request.form.get(f'status_{tank.id}', tank.status)
            if new_status in ('Full', 'Empty') and new_status != tank.status:
                old_status = tank.status
                tank.status = new_status
                changed += 1
                changes_desc.append(f'{tank.serial_number}: {old_status}→{new_status}')

                # Record history for each change
                history = TankHistory(
                    tank_id=tank.id,
                    event_type='Status Update',
                    event_description=f'Status updated {old_status}→{new_status} at {consumer.business_name}',
                    from_location='With Consumer',
                    to_location='With Consumer',
                    consumer_id=consumer.id,
                    created_by=current_user.id
                )
                db.session.add(history)

        if changed > 0:
            log = AuditLog(
                user_id=current_user.id,
                action='UPDATE',
                module='consumers',
                record_id=consumer.id,
                description=f'Updated {changed} tank status(es) for {consumer.business_name}: {"; ".join(changes_desc[:10])}{"..." if len(changes_desc) > 10 else ""}',
                ip_address=request.remote_addr
            )
            db.session.add(log)
            db.session.commit()
            flash(f'Updated {changed} tank(s) for {consumer.business_name}.', 'success')
        else:
            flash('No changes detected.', 'info')

        return redirect(url_for('consumers.view', id=id))

    # Build inventory data for the template
    tank_inventory = {}
    for s in SIZES:
        size_tanks = [t for t in tanks_here if t.tank_size == s]
        tank_inventory[s] = {
            'full':  sum(1 for t in size_tanks if t.status == 'Full'),
            'empty': sum(1 for t in size_tanks if t.status == 'Empty'),
            'total': len(size_tanks),
            'tanks': size_tanks,
        }

    total_full  = sum(v['full']  for v in tank_inventory.values())
    total_empty = sum(v['empty'] for v in tank_inventory.values())
    total_tanks = sum(v['total'] for v in tank_inventory.values())

    return render_template('consumers/update_tanks.html',
                           consumer=consumer,
                           tank_inventory=tank_inventory,
                           sizes=SIZES,
                           total_full=total_full,
                           total_empty=total_empty,
                           total_tanks=total_tanks)


# ──────────────────────────────────────────────────────
# DELETE (soft)
# ──────────────────────────────────────────────────────
@consumers_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.role != 'admin':
        flash('You do not have permission to delete consumers.', 'danger')
        return redirect(url_for('consumers.index'))
    consumer = Consumer.query.get_or_404(id)
    consumer.is_active = False
    log = AuditLog(user_id=current_user.id, action='DELETE', module='consumers',
                   record_id=consumer.id,
                   description=f'Deactivated consumer: {consumer.business_name}',
                   ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    flash('Consumer deactivated successfully.', 'warning')
    return redirect(url_for('consumers.index'))


# ──────────────────────────────────────────────────────
# BATCH DELETE (soft)
# ──────────────────────────────────────────────────────
@consumers_bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Permission denied.'}), 403

    consumer_ids = request.form.getlist('ids[]')
    if not consumer_ids:
        return jsonify({'success': False, 'message': 'No items selected.'}), 400

    count = 0
    for cid in consumer_ids:
        consumer = db.session.get(Consumer, int(cid))
        if consumer and consumer.is_active:
            consumer.is_active = False
            count += 1
            log = AuditLog(user_id=current_user.id, action='DELETE', module='consumers',
                           record_id=consumer.id,
                           description=f'Deactivated consumer (Batch): {consumer.business_name}',
                           ip_address=request.remote_addr)
            db.session.add(log)

    db.session.commit()
    flash(f'Successfully deactivated {count} consumers.', 'warning')
    return jsonify({'success': True, 'redirect': url_for('consumers.index')})
