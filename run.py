import sys

# Force UTF-8 output on Windows terminals
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')


from app import create_app, init_db, db
from app.models import User
import bcrypt

print("[DB] Using Neon PostgreSQL Online Database.")
app = create_app()

# Create tables and seed default admin
init_db(app)
print("[OK] Online sync ready.\n")


@app.shell_context_processor
def make_shell_context():
    return {'db': db, 'User': User}


@app.cli.command("create-admin")
def create_admin():
    """Create or reset the default admin user."""
    with app.app_context():
        db.create_all()
        existing = User.query.filter_by(username='admin').first()
        if not existing:
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
            print("[OK] Admin user created: admin / Admin@1234")
        else:
            print("[i] Admin user already exists.")


if __name__ == '__main__':
    print("=" * 50)
    print("  Gas Pinas Inc. -- LPG Management System (SYNCED)")
    print("  Database: Neon PostgreSQL (Cloud)")
    print("  URL: http://localhost:5001")
    print("  Login: admin / Admin@1234")
    print("=" * 50 + "\n")
    app.run(debug=True, host='0.0.0.0', port=5001)
