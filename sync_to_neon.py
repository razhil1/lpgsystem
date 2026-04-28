import os
import decimal
from sqlalchemy import create_engine, text, MetaData, Table
from app import create_app, db
from app.models import User, Consumer, Plant, Tank, Transaction, TransactionItem, Payment

def migrate():
    app = create_app()
    sqlite_path = os.path.join(app.instance_path, 'lpg_gaspinas.db')
    local_engine = create_engine(f"sqlite:///{sqlite_path}")
    remote_engine = create_engine(app.config['SQLALCHEMY_DATABASE_URI'])

    with app.app_context():
        print("[*] Resetting Neon schema...")
        with remote_engine.connect() as r_conn:
            r_conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; GRANT ALL ON SCHEMA public TO public;"))
            r_conn.commit()
        db.create_all()
        
        tables = [(User, 'users'), (Consumer, 'consumers'), (Plant, 'plants'), (Tank, 'tanks'), 
                  (Transaction, 'transactions'), (TransactionItem, 'transaction_items'), (Payment, 'payments')]

        for model, table_name in tables:
            print(f"[*] Migrating {table_name}...", end=" ", flush=True)
            with local_engine.connect() as l_conn:
                rows = [dict(r._mapping) for r in l_conn.execute(text(f"SELECT * FROM {table_name}"))]
            if not rows:
                print("Empty"); continue

            for r in rows:
                if table_name == 'transactions':
                    if 'type' in r: r['transaction_type'] = r.pop('type')
                    if 'user_id' in r: r['created_by'] = r.pop('user_id')
                for k, v in list(r.items()):
                    if k in ['is_active', 'has_serial_number']: r[k] = bool(v) if v is not None else None
                    if isinstance(v, float): r[k] = decimal.Decimal(str(v))

            with remote_engine.connect() as r_conn:
                t = Table(table_name, MetaData(), autoload_with=remote_engine, extend_existing=True)
                cols = [c.name for c in t.columns]
                filtered = [{k: v for k, v in r.items() if k in cols} for r in rows]
                r_conn.execute(t.insert(), filtered)
                try:
                    r_conn.execute(text(f"SELECT setval(pg_get_serial_sequence('{table_name}', 'id'), coalesce(max(id), 1), max(id) IS NOT null) FROM {table_name}"))
                except: pass
                r_conn.commit()
                print(f"Done ({len(filtered)})")
    print("\n[SUCCESS] Migration finished!")

if __name__ == "__main__": migrate()
