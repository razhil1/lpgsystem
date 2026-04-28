from flask import Blueprint, render_template, redirect, url_for, request, flash, jsonify
from flask_login import login_required, current_user
from app.models import Plant, AuditLog
from app.extensions import db

plants_bp = Blueprint('plants', __name__)


@plants_bp.route('/')
@login_required
def index():
    plants = Plant.query.filter_by(is_active=True).order_by(Plant.plant_name).all()
    return render_template('plants/index.html', plants=plants)


@plants_bp.route('/create', methods=['GET', 'POST'])
@login_required
def create():
    if request.method == 'POST':
        plant = Plant(
            plant_name=request.form['plant_name'],
            address=request.form.get('address'),
            contact_person=request.form.get('contact_person'),
            phone=request.form.get('phone'),
            refill_cost_11kg=request.form.get('refill_cost_11kg') or 0,
            refill_cost_11kg_fiber=request.form.get('refill_cost_11kg_fiber') or 0,
            refill_cost_22kg=request.form.get('refill_cost_22kg') or 0,
            refill_cost_50kg=request.form.get('refill_cost_50kg') or 0,
            refill_cost_industrial=request.form.get('refill_cost_industrial') or 0,
            notes=request.form.get('notes'),
        )
        db.session.add(plant)
        db.session.flush()
        log = AuditLog(user_id=current_user.id, action='CREATE', module='plants',
                       record_id=plant.id,
                       description=f'Created plant: {plant.plant_name}',
                       ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash(f'Plant "{plant.plant_name}" created.', 'success')
        return redirect(url_for('plants.index'))
    return render_template('plants/form.html', plant=None, action='Create')


@plants_bp.route('/<int:id>/view')
@login_required
def view(id):
    plant = Plant.query.get_or_404(id)
    return render_template('plants/view.html', plant=plant)



@plants_bp.route('/<int:id>/edit', methods=['GET', 'POST'])
@login_required
def edit(id):
    plant = Plant.query.get_or_404(id)
    if request.method == 'POST':
        plant.plant_name = request.form['plant_name']
        plant.address = request.form.get('address')
        plant.contact_person = request.form.get('contact_person')
        plant.phone = request.form.get('phone')
        plant.refill_cost_11kg = request.form.get('refill_cost_11kg') or 0
        plant.refill_cost_11kg_fiber = request.form.get('refill_cost_11kg_fiber') or 0
        plant.refill_cost_22kg = request.form.get('refill_cost_22kg') or 0
        plant.refill_cost_50kg = request.form.get('refill_cost_50kg') or 0
        plant.refill_cost_industrial = request.form.get('refill_cost_industrial') or 0
        plant.notes = request.form.get('notes')
        log = AuditLog(user_id=current_user.id, action='UPDATE', module='plants',
                       record_id=plant.id,
                       description=f'Updated plant: {plant.plant_name}',
                       ip_address=request.remote_addr)
        db.session.add(log)
        db.session.commit()
        flash('Plant updated.', 'success')
        return redirect(url_for('plants.index'))
    return render_template('plants/form.html', plant=plant, action='Edit')


@plants_bp.route('/<int:id>/delete', methods=['POST'])
@login_required
def delete(id):
    if current_user.role != 'admin':
        flash('No permission.', 'danger')
        return redirect(url_for('plants.index'))
    plant = Plant.query.get_or_404(id)
    plant.is_active = False
    db.session.commit()
    flash('Plant deactivated.', 'warning')
    return redirect(url_for('plants.index'))


# ──────────────────────────────────────────────────────
# BATCH DELETE (soft)
# ──────────────────────────────────────────────────────
@plants_bp.route('/batch-delete', methods=['POST'])
@login_required
def batch_delete():
    if current_user.role != 'admin':
        return jsonify({'success': False, 'message': 'Permission denied.'}), 403

    plant_ids = request.form.getlist('ids[]')
    if not plant_ids:
        return jsonify({'success': False, 'message': 'No items selected.'}), 400

    count = 0
    for pid in plant_ids:
        plant = db.session.get(Plant, int(pid))
        if plant and plant.is_active:
            plant.is_active = False
            count += 1
            log = AuditLog(user_id=current_user.id, action='DELETE', module='plants',
                           record_id=plant.id,
                           description=f'Deactivated plant (Batch): {plant.plant_name}',
                           ip_address=request.remote_addr)
            db.session.add(log)

    db.session.commit()
    flash(f'Successfully deactivated {count} plants.', 'warning')
    return jsonify({'success': True, 'redirect': url_for('plants.index')})
