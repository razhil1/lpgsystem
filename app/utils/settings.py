from app.models import SystemSetting
from flask import current_app

DEFAULT_SETTINGS = {
    'Business Name': ('Gas Pinas Inc.', 'Display name of the business'),
    'Business Address': ('123 Gas St, City', 'Office/Warehouse address'),
    'Contact Number': ('0912-345-6789', 'Main contact number'),
    'VAT Rate': ('12', 'VAT percentage for transactions'),
    'Currency Symbol': ('₱', 'Currency symbol for display'),
    
    'Tank Sizes': ('11kg, 11kg Fiber, 22kg, 50kg, Industrial', 'Available tank sizes in the system (comma separated)'),
    'Tank Categories': ('Old, New', 'Categories for tanks (comma separated)'),
    'Tank Statuses': ('Full, Empty, For Refill, Under Repair, Lost', 'Possible status values for tanks (comma separated)'),
    'Tank Locations': ('Warehouse, With Consumer, At Plant, In Transit', 'Possible locations for tanks (comma separated)'),
    'Consumer Types': ('Retailer, Company, Industrial, End-User', 'Types of consumers (comma separated)'),
    'Payment Methods': ('Cash, Bank Transfer, Check, GCash, Other', 'Accepted payment methods (comma separated)'),
    
    'Low Stock Threshold': ('10', 'Minimum quantity of small tanks to trigger alert'),
    'Enable Serial Tracking': ('True', 'Allow entering serial numbers for tanks'),
    'Maintenance Mode': ('False', 'Restrict site access to administrators only'),
    'Lost Status Name': ('Lost', 'The status value that identifies a tank as missing/lost'),
    'Warehouse Location Name': ('Warehouse', 'The location value representing the main storage'),
    
    'Invoice Prefix': ('INV', 'Prefix for transaction invoice numbers'),
    'Invoice Number Depth': ('5', 'Number of digits for invoice padding (e.g. 5 = 00001)'),
    'Auto-Serial Prefix': ('GP', 'Prefix for auto-generated tank serial numbers'),
    'Primary Color': ('#f97316', 'Main theme color for the application (HEX)'),
    'Log Retention Days': ('90', 'Number of days to keep audit logs'),
    'Session Timeout': ('60', 'User session timeout in minutes')
}

def get_setting(key, default='', is_list=False):
    """
    Get a system setting by key.
    If is_list=True, splits comma-separated string into a list.
    """
    if not default and key in DEFAULT_SETTINGS:
        default = DEFAULT_SETTINGS[key][0]
        
    try:
        setting = SystemSetting.query.filter_by(key=key).first()
        val = setting.value if setting else default
        
        if is_list:
            if not val:
                return []
            return [x.strip() for x in val.split(',')]
        
        return val
    except Exception:
        if is_list:
            return [x.strip() for x in default.split(',')] if default else []
        return default

