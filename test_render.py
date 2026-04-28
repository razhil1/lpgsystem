import traceback
import sys
sys.path.insert(0, r'd:\Development of system\FlaskAdminUI-1\LPG SYSTEM')
from app import create_app
app = create_app()
with app.app_context():
    try:
        t = app.jinja_env.get_template('transactions/return_form.html')
        print(t.render(consumers=[], current_user=None))
    except Exception as e:
        traceback.print_exc()
