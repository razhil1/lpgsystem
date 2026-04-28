from flask import Blueprint, render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user
from app.models import User, AuditLog
from app.extensions import db
import bcrypt
from datetime import datetime

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('dashboard.index'))

    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').encode()
        user = User.query.filter_by(username=username, is_active=True).first()

        if user and bcrypt.checkpw(password, user.password.encode()):
            login_user(user)
            user.last_login = datetime.utcnow()
            log = AuditLog(user_id=user.id, action='LOGIN', module='auth',
                           description=f'{user.full_name} logged in',
                           ip_address=request.remote_addr)
            db.session.add(log)
            db.session.commit()
            flash(f'Welcome back, {user.full_name}!', 'success')
            return redirect(url_for('dashboard.index'))
        else:
            flash('Invalid username or password.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/logout')
@login_required
def logout():
    log = AuditLog(user_id=current_user.id, action='LOGOUT', module='auth',
                   description=f'{current_user.full_name} logged out',
                   ip_address=request.remote_addr)
    db.session.add(log)
    db.session.commit()
    logout_user()
    flash('You have been logged out.', 'info')
    return redirect(url_for('auth.login'))
