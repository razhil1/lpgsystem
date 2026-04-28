from flask import Flask
from config import Config
from app.extensions import db, login_manager

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)

    # Register blueprints
    from app.auth.routes import auth_bp
    from app.dashboard.routes import dashboard_bp
    from app.tanks.routes import tanks_bp
    from app.consumers.routes import consumers_bp
    from app.plants.routes import plants_bp
    from app.transactions.routes import transactions_bp
    from app.reports.routes import reports_bp
    from app.reports.export import export_bp
    from app.settings.routes import settings_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(dashboard_bp, url_prefix='/')
    app.register_blueprint(tanks_bp, url_prefix='/tanks')
    app.register_blueprint(consumers_bp, url_prefix='/consumers')
    app.register_blueprint(plants_bp, url_prefix='/plants')
    app.register_blueprint(transactions_bp, url_prefix='/transactions')
    app.register_blueprint(reports_bp, url_prefix='/reports')
    app.register_blueprint(export_bp, url_prefix='/export')
    app.register_blueprint(settings_bp, url_prefix='/settings')
    
    # Template helpers
    from app.utils.settings import get_setting
    @app.context_processor
    def inject_settings():
        return dict(get_setting=get_setting)

    # ── Error Handlers ──────────────────────────────────────────────
    import traceback
    from flask import render_template
    from werkzeug.exceptions import HTTPException
    
    @app.errorhandler(404)
    def page_not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(Exception)
    def handle_exception(e):
        # Pass through HTTP errors
        if isinstance(e, HTTPException):
            return e
            
        print(f"\n[!] Global Exception Caught: {e}")
        tb = traceback.format_exc()
        return render_template('errors/500.html', error=str(e), traceback=tb), 500

    return app


def init_db(app):
    """Create tables and seed default admin. Call this after create_app()."""
    with app.app_context():
        try:
            db.create_all()
            from sqlalchemy import text
            try:
                db.session.execute(text("ALTER TABLE plants ADD COLUMN refill_cost_11kg_fiber NUMERIC(10, 2) DEFAULT 0"))
                db.session.commit()
            except Exception:
                db.session.rollback()

            try:
                db.session.execute(text("ALTER TABLE tanks ADD COLUMN tank_category VARCHAR(20) DEFAULT 'Old'"))
                db.session.commit()
            except Exception:
                db.session.rollback()

            try:
                db.session.execute(text("ALTER TABLE transaction_items ADD COLUMN tank_category VARCHAR(20)"))
                db.session.commit()
            except Exception:
                db.session.rollback()
            _seed_default_admin()
        except Exception as e:
            print(f"\n[!] Database init error: {e}\n")


def _seed_default_admin():
    from app.models import User
    import bcrypt
    try:
        if not User.query.filter_by(username='admin').first():
            hashed = bcrypt.hashpw('Admin@1234'.encode(), bcrypt.gensalt()).decode()
            admin = User(
                username='admin',
                password=hashed,
                full_name='System Administrator',
                role='admin',
                is_active=True
            )
            db.session.add(admin)
            db.session.commit()
            print("[OK] Default admin created: admin / Admin@1234")
    except Exception:
        pass
