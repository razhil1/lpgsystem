from datetime import datetime
from flask_login import UserMixin
from app.extensions import db


# ─────────────────────────────────────────
# USERS
# ─────────────────────────────────────────
class User(UserMixin, db.Model):
    __tablename__ = 'lpg_users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password = db.Column(db.String(255), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    role = db.Column(db.String(20), default='staff', nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime, nullable=True)

    def __repr__(self):
        return f'<User {self.username}>'


# Flask-Login user loader
from app.extensions import login_manager

@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# ─────────────────────────────────────────
# CONSUMERS
# ─────────────────────────────────────────
class Consumer(db.Model):
    __tablename__ = 'lpg_consumers'
    id = db.Column(db.Integer, primary_key=True)
    consumer_code = db.Column(db.String(20), unique=True, nullable=False)
    business_name = db.Column(db.String(150), nullable=False)
    contact_person = db.Column(db.String(100))
    address = db.Column(db.Text)
    phone = db.Column(db.String(50))
    email = db.Column(db.String(100))
    consumer_type = db.Column(db.String(30), default='End-User', nullable=False)
    credit_limit = db.Column(db.Numeric(12, 2), default=0)
    outstanding_balance = db.Column(db.Numeric(12, 2), default=0)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('lpg_users.id'))

    transactions = db.relationship('Transaction', backref='consumer', lazy='dynamic')

    def __repr__(self):
        return f'<Consumer {self.business_name}>'


# ─────────────────────────────────────────
# PLANTS
# ─────────────────────────────────────────
class Plant(db.Model):
    __tablename__ = 'lpg_plants'
    id = db.Column(db.Integer, primary_key=True)
    plant_name = db.Column(db.String(150), nullable=False)
    address = db.Column(db.Text)
    contact_person = db.Column(db.String(100))
    phone = db.Column(db.String(50))
    refill_cost_11kg = db.Column(db.Numeric(10, 2), default=0)
    refill_cost_11kg_fiber = db.Column(db.Numeric(10, 2), default=0)
    refill_cost_22kg = db.Column(db.Numeric(10, 2), default=0)
    refill_cost_50kg = db.Column(db.Numeric(10, 2), default=0)
    refill_cost_industrial = db.Column(db.Numeric(10, 2), default=0)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Plant {self.plant_name}>'


# ─────────────────────────────────────────
# TANKS
# ─────────────────────────────────────────
class Tank(db.Model):
    __tablename__ = 'lpg_tanks'
    id = db.Column(db.Integer, primary_key=True)
    # serial_number is auto-generated if not provided (GP-YYYYMMDD-XXXX)
    serial_number = db.Column(db.String(50), unique=True, nullable=True)
    # True = user-provided serial, False = auto-generated internal code
    has_serial_number = db.Column(db.Boolean, default=False)
    # Groups tanks added in the same batch registration
    batch_code = db.Column(db.String(30), nullable=True, index=True)
    tank_size = db.Column(db.String(20), nullable=False)
    tank_category = db.Column(db.String(20), default='Old', nullable=False)
    brand = db.Column(db.String(50))
    status = db.Column(db.String(20), default='Empty', nullable=False)
    location = db.Column(db.String(30), default='Warehouse', nullable=False)
    current_consumer_id = db.Column(db.Integer, db.ForeignKey('lpg_consumers.id'), nullable=True)
    current_plant_id = db.Column(db.Integer, db.ForeignKey('lpg_plants.id'), nullable=True)
    purchase_date = db.Column(db.Date, nullable=True)
    purchase_cost = db.Column(db.Numeric(10, 2), default=0)
    last_transaction_date = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('lpg_users.id'))

    current_consumer = db.relationship('Consumer', foreign_keys=[current_consumer_id])
    current_plant = db.relationship('Plant', foreign_keys=[current_plant_id])
    history = db.relationship('TankHistory', backref='tank', lazy='dynamic', order_by='TankHistory.created_at.desc()')

    @property
    def display_code(self):
        """What to show in the UI — serial if available, else auto-code."""
        return self.serial_number or '—'

    def __repr__(self):
        return f'<Tank {self.serial_number}>'


# ─────────────────────────────────────────
# TRANSACTIONS
# ─────────────────────────────────────────
class Transaction(db.Model):
    __tablename__ = 'lpg_transactions'
    id = db.Column(db.Integer, primary_key=True)
    invoice_no = db.Column(db.String(30), unique=True, nullable=False)
    transaction_type = db.Column(db.String(20), nullable=False)
    transaction_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    consumer_id = db.Column(db.Integer, db.ForeignKey('lpg_consumers.id'), nullable=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('lpg_plants.id'), nullable=True)
    driver_name = db.Column(db.String(100))
    truck_plate = db.Column(db.String(20))
    total_amount = db.Column(db.Numeric(12, 2), default=0)
    amount_paid = db.Column(db.Numeric(12, 2), default=0)
    payment_status = db.Column(db.String(20), default='Unpaid')
    remarks = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('lpg_users.id'))

    plant = db.relationship('Plant', foreign_keys=[plant_id])
    items = db.relationship('TransactionItem', backref='transaction', lazy='dynamic', cascade='all, delete-orphan')
    payments = db.relationship('Payment', backref='transaction', lazy='dynamic', cascade='all, delete-orphan')
    creator = db.relationship('User', foreign_keys=[created_by])

    @property
    def balance(self):
        return float(self.total_amount or 0) - float(self.amount_paid or 0)

    @property
    def days_outstanding(self):
        from datetime import date
        if self.transaction_date:
            d = self.transaction_date
            if hasattr(d, 'date'):
                d = d.date()
            return (date.today() - d).days
        return 0

    @property
    def total_qty(self):
        """Total number of tanks across all line items."""
        return sum(item.quantity or 1 for item in self.items)

    @property
    def qty_by_size(self):
        """Dict of {tank_size: qty} for quantity breakdown by size."""
        result = {}
        for item in self.items:
            size = (item.tank.tank_size if item.tank else item.tank_size) or '?'
            cat = (item.tank.tank_category if item.tank else item.tank_category) or 'Old'
            key = f"{size} ({cat})"
            result[key] = result.get(key, 0) + (item.quantity or 1)
        return result

    def __repr__(self):
        return f'<Transaction {self.invoice_no}>'


class TransactionItem(db.Model):
    __tablename__ = 'lpg_transaction_items'
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('lpg_transactions.id'), nullable=False)
    # tank_id is NULL for quantity-based items (no serial tracking)
    tank_id = db.Column(db.Integer, db.ForeignKey('lpg_tanks.id'), nullable=True)
    tank_size = db.Column(db.String(20), nullable=True)   # e.g. '11kg', for qty-based
    tank_category = db.Column(db.String(20), nullable=True)
    quantity = db.Column(db.Integer, default=1)
    unit_price = db.Column(db.Numeric(10, 2), default=0)
    refill_cost = db.Column(db.Numeric(10, 2), default=0)
    condition = db.Column(db.String(50))  # For returns: Good / Damaged

    tank = db.relationship('Tank', foreign_keys=[tank_id])

    @property
    def subtotal(self):
        return float(self.unit_price or 0) * int(self.quantity or 1)


# ─────────────────────────────────────────
# PAYMENTS
# ─────────────────────────────────────────
class Payment(db.Model):
    __tablename__ = 'lpg_payments'
    id = db.Column(db.Integer, primary_key=True)
    transaction_id = db.Column(db.Integer, db.ForeignKey('lpg_transactions.id'), nullable=False)
    payment_date = db.Column(db.Date, nullable=False, default=datetime.utcnow)
    amount = db.Column(db.Numeric(12, 2), nullable=False)
    payment_method = db.Column(db.String(30), default='Cash')
    reference_no = db.Column(db.String(100))
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('lpg_users.id'))


# ─────────────────────────────────────────
# TANK HISTORY
# ─────────────────────────────────────────
class TankHistory(db.Model):
    __tablename__ = 'lpg_tank_history'
    id = db.Column(db.Integer, primary_key=True)
    tank_id = db.Column(db.Integer, db.ForeignKey('lpg_tanks.id'), nullable=False)
    transaction_id = db.Column(db.Integer, db.ForeignKey('lpg_transactions.id'), nullable=True)
    event_type = db.Column(db.String(50), nullable=False)  # Delivered, Returned, Sent to Plant, etc.
    event_description = db.Column(db.Text)
    from_location = db.Column(db.String(100))
    to_location = db.Column(db.String(100))
    consumer_id = db.Column(db.Integer, db.ForeignKey('lpg_consumers.id'), nullable=True)
    plant_id = db.Column(db.Integer, db.ForeignKey('lpg_plants.id'), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_by = db.Column(db.Integer, db.ForeignKey('lpg_users.id'))

    consumer = db.relationship('Consumer', foreign_keys=[consumer_id])
    plant = db.relationship('Plant', foreign_keys=[plant_id])
    creator = db.relationship('User', foreign_keys=[created_by], lazy='select')


# ─────────────────────────────────────────
# AUDIT LOGS
# ─────────────────────────────────────────
class AuditLog(db.Model):
    __tablename__ = 'lpg_audit_logs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('lpg_users.id'), nullable=True)
    action = db.Column(db.String(50), nullable=False)   # CREATE, UPDATE, DELETE, LOGIN, etc.
    module = db.Column(db.String(50), nullable=False)   # tanks, consumers, transactions, etc.
    record_id = db.Column(db.Integer, nullable=True)
    description = db.Column(db.Text)
    ip_address = db.Column(db.String(50))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User', foreign_keys=[user_id])


# ─────────────────────────────────────────
# SYSTEM SETTINGS
# ─────────────────────────────────────────
class SystemSetting(db.Model):
    __tablename__ = 'lpg_system_settings'
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(50), unique=True, nullable=False)
    value = db.Column(db.Text)
    description = db.Column(db.String(255))
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<SystemSetting {self.key}: {self.value}>'
