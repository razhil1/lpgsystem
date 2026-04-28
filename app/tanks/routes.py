from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app.models import Tank, TankHistory, AuditLog
from app.extensions import db
from datetime import datetime, date
from app.utils.settings import get_setting

tanks_bp = Blueprint('tanks', __name__)


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


def _auto_serial(size_code, seq):
    """Generate internal code like GP-11KG-00042 when no serial is provided."""
    prefix = get_setting('Auto-Serial Prefix', default='GP')
    return f"{prefix}-{size_code.upper().replace('KG','')}-{seq:05d}"


def _next_seq():
    """Get next auto-serial sequence number based on current count."""
    return Tank.query.count() + 1


def _batch_code():
    """Generate batch code like BATCH-20240305-0001."""
    return f"BATCH-{date.today().strftime('%Y%m%d')}-{_next_seq():04d}"


# ──────────────────────────────────────────────────────
# LIST
# ──────────────────────────────────────────────────────
@tanks_bp.route('/')
@login_required
def index():
    search = request.args.get('search', '')
    size = request.args.get('size', '')
    status = request.args.get('status', '')
    location = request.args.get('location', '')
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 25, type=int)

    q = Tank.query.filter_by(is_active=True)
    if search:
        q = q.filter(Tank.serial_number.ilike(f'%{search}%'))
    if size:
        q = q.filter(Tank.tank_size == size)
    if status:
        q = q.filter(Tank.status == status)
    if location:
        q = q.filter(Tank.location == location)

    tanks = q.order_by(Tank.id.desc()).paginate(page=page, per_page=per_page)

    # Summary counts per size
    size_summary = {}
    for s in get_setting('Tank Sizes', is_list=True):
        size_summary[s] = {
            'total': Tank.query.filter_by(tank_size=s, is_active=True).count(),
            'full': Tank.query.filter_by(tank_size=s, status='Full', is_active=True).count(),
            'empty': Tank.query.filter_by(tank_size=s, status='Empty', is_active=True).count(),
            'warehouse': Tank.query.filter_by(tank_size=s, location='Warehouse', is_active=True).count(),
        }

    return render_template('tanks/index.html', tanks=tanks,
                           search=search, size=size, status=status, location=location,
                           per_page=per_page, size_summary=size_summary)


# ──────────────────────────────────────────────────────
# CREATE — batch mode (quantity, no serial required)
# ──────────────────────────────────────────────────────
@tanks_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        tank_size = request.form['tank_size']
        tank_category = request.form.get('tank_category', 'Old')
        quantity = int(request.form.get('quantity', 1))
        brand = request.form.get('brand', '')
        status = request.form.get('status', 'Empty')
        location = request.form.get('location', 'Warehouse')
        purchase_date = parse_date(request.form.get('purchase_date'))
        purchase_cost = request.form.get('purchase_cost') or 0
        notes = request.form.get('notes', '')
        use_serial = request.form.get('use_serial') == '1'
        serial_input = request.form.get('serial_number', '').strip().upper()

        if quantity < 1 or quantity > 500:
            flash('Quantity must be between 1 and 500.', 'danger')
            return render_template('tanks/form.html', tank=None, action='Add')

        # Single tank with a serial number
        if use_serial and serial_input:
            if Tank.query.filter_by(serial_number=serial_input).first():
                flash(f'Serial number "{serial_input}" already exists.', 'danger')
                return render_template('tanks/form.html', tank=None, action='Add')
            quantity = 1  # override

        batch = _batch_code()
        created_tanks = []

        for i in range(quantity):
            seq = _next_seq() + i

            # Determine serial number
            if use_serial and serial_input and i == 0:
                sn = serial_input
                has_sn = True
            else:
                sn = _auto_serial(tank_size, seq)
                has_sn = False

            # Make sure auto-generated SN is unique (rare edge case)
            while Tank.query.filter_by(serial_number=sn).first():
                seq += 1
                sn = _auto_serial(tank_size, seq)

            tank = Tank(
                serial_number=sn,
                has_serial_number=has_sn,
                batch_code=batch,
                tank_size=tank_size,
                tank_category=tank_category,
                brand=brand,
                status=status,
                location=location,
                purchase_date=purchase_date,
                purchase_cost=purchase_cost,
                notes=notes,
                created_by=current_user.id
            )
            db.session.add(tank)
            db.session.flush()

            history = TankHistory(
                tank_id=tank.id,
                event_type='Registered',
                event_description=f'Registered in batch {batch} ({tank_size})',
                from_location='N/A',
                to_location=location,
                created_by=current_user.id
            )
            db.session.add(history)
            created_tanks.append(tank)

        log = AuditLog(
            user_id=current_user.id, action='CREATE', module='tanks',
            description=f'Batch registered {quantity} x {tank_size} tanks (Batch: {batch})',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()

        if quantity == 1:
            flash(f'Tank registered successfully.', 'success')
        else:
            flash(f'{quantity} × {tank_size} tanks registered successfully! (Batch: {batch})', 'success')

        return redirect(url_for('tanks.index'))

    return render_template('tanks/form.html', tank=None, action='Add')


# ──────────────────────────────────────────────────────
# EDIT
# ──────────────────────────────────────────────────────
@tanks_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    tank = Tank.query.get_or_404(id)
    if request.method == 'POST':
        old_status = tank.status
        old_location = tank.location

        # Only update serial if provided and different
        new_sn = request.form.get('serial_number', '').strip().upper()
        if new_sn and new_sn != tank.serial_number:
            existing = Tank.query.filter_by(serial_number=new_sn).first()
            if existing and existing.id != tank.id:
                flash(f'Serial number "{new_sn}" already exists.', 'danger')
                return render_template('tanks/form.html', tank=tank, action='Edit')
            tank.serial_number = new_sn
            tank.has_serial_number = True

        tank.tank_size = request.form['tank_size']
        tank.tank_category = request.form.get('tank_category', 'Old')
        tank.brand = request.form.get('brand')
        tank.status = request.form.get('status', tank.status)
        tank.location = request.form.get('location', tank.location)
        tank.purchase_date = parse_date(request.form.get('purchase_date'))
        tank.purchase_cost = request.form.get('purchase_cost') or 0
        tank.notes = request.form.get('notes')

        if old_status != tank.status or old_location != tank.location:
            history = TankHistory(
                tank_id=tank.id,
                event_type='Manual Update',
                event_description=f'Status: {old_status}→{tank.status} | Location: {old_location}→{tank.location}',
                from_location=old_location,
                to_location=tank.location,
                created_by=current_user.id
            )
            db.session.add(history)

        log = AuditLog(user_id=current_user.id, action='UPDATE', module='tanks',
                       record_id=tank.id,
                       description=f'Updated tank: {tank.serial_number}',
                       ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash('Tank updated successfully.', 'success')
        return redirect(url_for('tanks.index'))

    return render_template('tanks/form.html', tank=tank, action='Edit')


# ──────────────────────────────────────────────────────
# VIEW detail + history
# ──────────────────────────────────────────────────────
@tanks_bp.route('/<int:id>/view')
@login_required
def view(id):
    tank = Tank.query.get_or_404(id)
    history = tank.history.all()
    return render_template('tanks/view.html', tank=tank, history=history)


# ──────────────────────────────────────────────────────
# DELETE (soft)
# ──────────────────────────────────────────────────────
@tanks_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.role != 'admin':
        flash('You do not have permission to delete tanks.', 'danger')
        return redirect(url_for('tanks.index'))
    
    tank = Tank.query.get_or_404(id)
    
    # Delete associated history records first
    for h in tank.history:
        db.session.delete(h)
        
    log = AuditLog(user_id=current_user.id, action='DELETE', module='tanks',
                   record_id=tank.id,
                   description=f'Deleted tank permanently: {tank.serial_number}',
                   ip_address=request.remote_addr)
    
    db.session.delete(tank)
    db.session.add(log)
    db.session.commit()
    
    flash('Tank deleted permanently.', 'warning')
    return redirect(url_for('tanks.index'))


# ──────────────────────────────────────────────────────
# BATCH DELETE (soft)
# ──────────────────────────────────────────────────────
@tanks_bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Permission denied.'}), 403

    tank_ids = request.form.getlist('ids[]')
    if not tank_ids:
        return jsonify({'success': False, 'message': 'No items selected.'}), 400

    count = 0
    for tid in tank_ids:
        tank = db.session.get(Tank, int(tid))
        if tank:
            # Delete associated history records first to satisfy foreign key constraints
            for h in tank.history:
                db.session.delete(h)
            
            db.session.delete(tank)
            count += 1
            log = AuditLog(user_id=current_user.id, action='DELETE', module='tanks',
                           record_id=tank.id,
                           description=f'Deleted tank permanently (Batch): {tank.serial_number}',
                           ip_address=request.remote_addr)
            db.session.add(log)

    db.session.commit()
    flash(f'Successfully deleted {count} tanks permanently.', 'warning')
    return jsonify({'success': True, 'redirect': url_for('tanks.index')})


# ──────────────────────────────────────────────────────
# API: Stock summary by size (for delivery form)
# ──────────────────────────────────────────────────────
@tanks_bp.route('/api/stock-summary')
@login_required
def stock_summary():
    result = {}
    for s in ['11kg', '11kg Fiber', '22kg', '50kg', 'Industrial']:
        result[s] = {
            'full_warehouse': Tank.query.filter_by(
                tank_size=s, status='Full', location='Warehouse', is_active=True
            ).count(),
            'empty_warehouse': Tank.query.filter_by(
                tank_size=s, status='Empty', location='Warehouse', is_active=True
            ).count(),
        }
    return jsonify(result)
# ──────────────────────────────────────────────────────
# MARK AS LOST
# ──────────────────────────────────────────────────────
@tanks_bp.route('/<int:id>/mark-lost', methods=['POST'])
@login_required
def mark_lost(id):
    if current_user.role != 'admin':
        flash('Permission denied.', 'danger')
        return redirect(url_for('tanks.view', id=id))
    
    tank = Tank.query.get_or_404(id)
    if tank.status == 'Lost':
        flash('Tank is already marked as lost.', 'info')
        return redirect(url_for('tanks.view', id=id))
    
    old_status = tank.status
    tank.status = 'Lost'
    
    history = TankHistory(
        tank_id=tank.id,
        event_type='Lost',
        event_description=f'Cylinder marked as Lost (Previous status: {old_status})',
        from_location=tank.location,
        to_location=tank.location,
        created_by=current_user.id
    )
    db.session.add(history)
    
    log = AuditLog(
        user_id=current_user.id,
        action='UPDATE',
        module='tanks',
        record_id=id,
        description=f'Marked tank {tank.serial_number} as lost',
        ip_address=request.remote_addr
    )
    db.session.add(log)
    db.session.commit()
    
    flash(f'Tank {tank.serial_number} marked as lost.', 'warning')
    return redirect(url_for('tanks.view', id=id))
