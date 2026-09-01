from flask import Blueprint, redirect, render_template, url_for
from flask_login import login_user, logout_user, login_required

from app.extensions import bcrypt, db
from app.models import User
from app.auth.forms import LoginForm, RegisterForm


auth_bp = Blueprint("auth", __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password_hashed, form.password.data):
            login_user(user)
            return redirect(url_for('students.index'))
        else:
            return render_template('login.html', form=form, title='Login', error='Invalid email or password.')
    return render_template('login.html', form=form, title='Login')


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Create new user
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(email=form.email.data, password_hashed=hashed_password)
        db.session.add(user)
        db.session.commit()
        print(f"Registered new user: {user.email}")
        return redirect(url_for('auth.login'))
    return render_template('register.html', form=form, title='Register')


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))