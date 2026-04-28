from flask import Blueprint, render_template, request, make_response
from flask_login import login_required, current_user
from app.models import Transaction, Tank, Consumer, Payment, TankHistory, AuditLog
from app.extensions import db
from sqlalchemy import func
from datetime import datetime, date, timedelta
from app.utils.settings import get_setting
import io

reports_bp = Blueprint('reports', __name__)


def get_date_range():
    """Return (date_from, date_to) as Python date objects for SQLite queries,
    also as ISO strings for passing back to templates."""
    date_from_str = request.args.get('date_from', date.today().replace(day=1).isoformat())
    date_to_str = request.args.get('date_to', date.today().isoformat())
    try:
        date_from = datetime.strptime(date_from_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        date_from = date.today().replace(day=1)
    try:
        date_to = datetime.strptime(date_to_str, '%Y-%m-%d').date()
    except (ValueError, TypeError):
        date_to = date.today()
    return date_from, date_to


@reports_bp.route('/')
@login_required
def index():
    return render_template('reports/index.html')


@reports_bp.route('/sales')
@login_required
def sales():
    date_from, date_to = get_date_range()
    consumer_id = request.args.get('consumer_id', '')
    tank_size = request.args.get('tank_size', '')

    q = Transaction.query.filter(
        Transaction.transaction_type == 'Delivery',
        Transaction.transaction_date >= date_from,
        Transaction.transaction_date <= date_to
    )
    if consumer_id:
        q = q.filter(Transaction.consumer_id == consumer_id)

    transactions = q.order_by(Transaction.transaction_date.desc()).all()
    total_sales = sum(float(t.total_amount or 0) for t in transactions)
    total_paid = sum(float(t.amount_paid or 0) for t in transactions)
    total_outstanding = total_sales - total_paid

    consumers = Consumer.query.filter_by(is_active=True).order_by(Consumer.business_name).all()

    return render_template('reports/sales.html',
                           transactions=transactions,
                           total_sales=total_sales,
                           total_paid=total_paid,
                           total_outstanding=total_outstanding,
                           consumers=consumers,
                           date_from=date_from.isoformat(),
                           date_to=date_to.isoformat(),
                           consumer_id=consumer_id)


@reports_bp.route('/tank-movement')
@login_required
def tank_movement():
    date_from, date_to = get_date_range()
    tank_sn = request.args.get('tank_sn', '')

    q = TankHistory.query.filter(
        TankHistory.created_at >= date_from
    )
    try:
        if isinstance(date_to, str):
            date_to_dt = datetime.strptime(date_to, '%Y-%m-%d').replace(hour=23, minute=59, second=59)
        else:
            date_to_dt = datetime.combine(date_to, datetime.max.time())
        q = q.filter(TankHistory.created_at <= date_to_dt)
    except ValueError:
        pass
    if tank_sn:
        tank = Tank.query.filter_by(serial_number=tank_sn.upper()).first()
        if tank:
            q = q.filter(TankHistory.tank_id == tank.id)

    history = q.order_by(TankHistory.created_at.desc()).all()
    return render_template('reports/tank_movement.html',
                           history=history,
                           date_from=date_from.isoformat(),
                           date_to=date_to.isoformat(),
                           tank_sn=tank_sn)


@reports_bp.route('/tank-status')
@login_required
def tank_status():
    sizes = get_setting('Tank Sizes', is_list=True)
    statuses = get_setting('Tank Statuses', is_list=True)
    locations = get_setting('Tank Locations', is_list=True)

    summary = {}
    for size in sizes:
        summary[size] = {}
        for status in statuses:
            count = Tank.query.filter_by(tank_size=size, status=status, is_active=True).count()
            summary[size][status] = count

    location_summary = {}
    for loc in locations:
        count = Tank.query.filter_by(location=loc, is_active=True).count()
        location_summary[loc] = count

    return render_template('reports/tank_status.html',
                           summary=summary, sizes=sizes, statuses=statuses,
                           location_summary=location_summary)


@reports_bp.route('/outstanding')
@login_required
def outstanding():
    consumers = Consumer.query.filter(
        Consumer.outstanding_balance > 0,
        Consumer.is_active == True
    ).order_by(Consumer.outstanding_balance.desc()).all()

    unpaid_txns = Transaction.query.filter(
        Transaction.payment_status.in_(['Unpaid', 'Partial']),
        Transaction.transaction_type == 'Delivery'
    ).order_by(Transaction.transaction_date).all()

    today = date.today()
    # Note: txn.days_outstanding is already a @property on the Transaction model,
    # so we don't need to assign it here.

    return render_template('reports/outstanding.html',
                           consumers=consumers, transactions=unpaid_txns)


@reports_bp.route('/missing-tanks')
@login_required
def missing_tanks():
    """Report on tanks marked as 'Lost' (configurable)."""
    lost_status = get_setting('Lost Status Name', default='Lost')
    tanks = Tank.query.filter_by(status=lost_status, is_active=True).all()
    return render_template('reports/missing_tanks.html', tanks=tanks)


@reports_bp.route('/audit-trail')
@login_required
def audit_trail():
    page = request.args.get('page', 1, type=int)
    logs = AuditLog.query.order_by(
        AuditLog.created_at.desc()
    ).paginate(page=page, per_page=30)
    return render_template('reports/audit_trail.html', logs=logs)
