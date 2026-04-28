from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_required, current_user
from app.models import SystemSetting, AuditLog
from app.extensions import db

settings_bp = Blueprint('settings', __name__)

@settings_bp.route('/', methods=['GET', 'POST'])
@login_required
def index():
    if current_user.role != 'admin':
        flash('Permission denied.', 'danger')
        return redirect(url_for('dashboard.index'))
    
    if request.method == 'POST':
        # Handles update of existing settings
        processed_keys = []
        for key, value in request.form.items():
            if key.startswith('setting_'):
                setting_key = key.replace('setting_', '')
                setting = SystemSetting.query.filter_by(key=setting_key).first()
                if setting:
                    setting.value = value
                    processed_keys.append(setting_key)
        
        db.session.commit()
        
        log = AuditLog(
            user_id=current_user.id,
            action='UPDATE',
            module='settings',
            description=f'Updated system settings: {", ".join(processed_keys)}',
            ip_address=request.remote_addr
        )
        db.session.add(log)
        db.session.commit()
        
        flash('Settings updated successfully.', 'success')
        return redirect(url_for('settings.index'))

    settings = SystemSetting.query.all()
    
    # Initialize defaults if empty
    if not settings:
        defaults = [
            # Core Business Info
            ('Business Name', 'Gas Pinas Inc.', 'Display name of the business'),
            ('Business Address', '123 Gas St, City', 'Office/Warehouse address'),
            ('Contact Number', '0912-345-6789', 'Main contact number'),
            ('VAT Rate', '12', 'VAT percentage for transactions'),
            ('Currency Symbol', '₱', 'Currency symbol for display'),
            
            # System Configuration Lists (Comma separated)
            ('Tank Sizes', '11kg, 11kg Fiber, 22kg, 50kg, Industrial', 'Available tank sizes in the system (comma separated)'),
            ('Tank Categories', 'Old, New', 'Categories for tanks (comma separated)'),
            ('Tank Statuses', 'Full, Empty, For Refill, Under Repair, Lost', 'Possible status values for tanks (comma separated)'),
            ('Tank Locations', 'Warehouse, With Consumer, At Plant, In Transit', 'Possible locations for tanks (comma separated)'),
            ('Consumer Types', 'Retailer, Company, Industrial, End-User', 'Types of consumers (comma separated)'),
            ('Payment Methods', 'Cash, Bank Transfer, Check, GCash, Other', 'Accepted payment methods (comma separated)'),
            
            # Feature Toggles / Thresholds
            ('Low Stock Threshold', '10', 'Minimum quantity of small tanks to trigger alert'),
            ('Enable Serial Tracking', 'True', 'Allow entering serial numbers for tanks'),
            ('Maintenance Mode', 'False', 'Restrict site access to administrators only'),
            ('Lost Status Name', 'Lost', 'The status value that identifies a tank as missing/lost'),
            ('Warehouse Location Name', 'Warehouse', 'The location value representing the main storage'),
            
            # Advanced Features
            ('Invoice Prefix', 'INV', 'Prefix for transaction invoice numbers'),
            ('Invoice Number Depth', '5', 'Number of digits for invoice padding (e.g. 5 = 00001)'),
            ('Auto-Serial Prefix', 'GP', 'Prefix for auto-generated tank serial numbers'),
            ('Primary Color', '#f97316', 'Main theme color for the application (HEX)'),
            ('Log Retention Days', '90', 'Number of days to keep audit logs'),
            ('Session Timeout', '60', 'User session timeout in minutes')
        ]
        for k, v, d in defaults:
            s = SystemSetting(key=k, value=v, description=d)
            db.session.add(s)
        db.session.commit()
        settings = SystemSetting.query.all()

    return render_template('settings/index.html', settings=settings)
