from flask import Blueprint, render_template
from flask_login import login_required
from app.models import Tank, Consumer, Transaction, Payment
from app.extensions import db
from sqlalchemy import func
from datetime import datetime, date, timedelta
from app.utils.settings import get_setting

dashboard_bp = Blueprint('dashboard', __name__)


@dashboard_bp.route('/')
@login_required
def index():
    # Tank stats
    total_tanks = Tank.query.filter_by(is_active=True).count()
    wh_name = get_setting('Warehouse Location Name', default='Warehouse')
    tanks_warehouse = Tank.query.filter_by(location=wh_name, is_active=True).count()
    tanks_consumer = Tank.query.filter_by(location='With Consumer', is_active=True).count()
    tanks_plant = Tank.query.filter_by(location='At Plant', is_active=True).count()
    tanks_full = Tank.query.filter_by(status='Full', is_active=True).count()
    tanks_empty = Tank.query.filter_by(status='Empty', is_active=True).count()

    # Sales today
    today = date.today()
    today_sales = db.session.query(func.sum(Transaction.total_amount)).filter(
        Transaction.transaction_date == today,
        Transaction.transaction_type == 'Delivery'
    ).scalar() or 0

    # Sales this month
    month_start = today.replace(day=1)
    monthly_sales = db.session.query(func.sum(Transaction.total_amount)).filter(
        Transaction.transaction_date >= month_start,
        Transaction.transaction_type == 'Delivery'
    ).scalar() or 0

    # Outstanding receivables
    outstanding = db.session.query(
        func.sum(Transaction.total_amount - Transaction.amount_paid)
    ).filter(
        Transaction.payment_status.in_(['Unpaid', 'Partial']),
        Transaction.transaction_type == 'Delivery'
    ).scalar() or 0

    # Recent transactions (last 10)
    recent_transactions = Transaction.query.order_by(
        Transaction.created_at.desc()
    ).limit(10).all()

    # Monthly sales chart data (last 6 months)
    chart_labels = []
    chart_data = []
    for i in range(5, -1, -1):
        d = today - timedelta(days=i * 30)
        m_start = d.replace(day=1)
        if d.month == 12:
            m_end = d.replace(year=d.year + 1, month=1, day=1) - timedelta(days=1)
        else:
            m_end = d.replace(month=d.month + 1, day=1) - timedelta(days=1)
        total = db.session.query(func.sum(Transaction.total_amount)).filter(
            Transaction.transaction_date >= m_start,
            Transaction.transaction_date <= m_end,
            Transaction.transaction_type == 'Delivery'
        ).scalar() or 0
        chart_labels.append(d.strftime('%b %Y'))
        chart_data.append(float(total))

    # Consumer count
    total_consumers = Consumer.query.filter_by(is_active=True).count()

    return render_template('dashboard/index.html',
        total_tanks=total_tanks,
        tanks_warehouse=tanks_warehouse,
        tanks_consumer=tanks_consumer,
        tanks_plant=tanks_plant,
        tanks_full=tanks_full,
        tanks_empty=tanks_empty,
        today_sales=today_sales,
        monthly_sales=monthly_sales,
        outstanding=outstanding,
        recent_transactions=recent_transactions,
        chart_labels=chart_labels,
        chart_data=chart_data,
        total_consumers=total_consumers,
    )
