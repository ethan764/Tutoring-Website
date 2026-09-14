from flask import Blueprint, redirect, render_template, url_for
from flask_login import login_user, logout_user, login_required
from secrets import token_urlsafe
from email_interactor import send_email
from datetime import datetime
import os

from app.extensions import bcrypt, db
from app.models import User
from app.auth.forms import LoginForm, RegisterForm, ResendCodeForm


auth_bp = Blueprint("auth", __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            return render_template('login.html', form=form, title='Login', error='No User Found. Register Instead.')

        if user.verified == False:
            return render_template('login.html', form=form, title='Login', error='The account has not been verified.')

        if user and bcrypt.check_password_hash(user.password_hashed, form.password.data):
            login_user(user)
            return redirect(url_for('students.student_portal'))
        else:
            return render_template('login.html', form=form, title='Login', error='Invalid email or password.')
    return render_template('login.html', form=form, title='Login')




# maybe add this to a service later
def send_confirmation_link(user):
    # validation code
    email_verify_token = token_urlsafe(32)
    hashed_email_verify_token = bcrypt.generate_password_hash(email_verify_token).decode('utf-8')

    try:
        print('test')
        send_email(to_email=user.email,
                    subject="Email Verification",
                    use_html=False,
                    body=f"""
Hello,
Please verify your email by clicking on the link below.
{url_for('auth.verify_email', user_id=user.id, email_verification_code=email_verify_token)}

Thank you for choosing my tutoring services!
Regards, 
Ethan

(This is an automated message. I'll still respond if you wish to reply)
"""
                    )
    except Exception as e:
        print(e)

    return hashed_email_verify_token

@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Create new user
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')

        user = User(email=form.email.data, password_hashed=hashed_password)        
        db.session.add(user)

        hashed_email_verify_token = send_confirmation_link(user)
        user.link_code_hashed = hashed_email_verify_token
        db.session.commit()


        print(f"Registered new user: {user.email}")
        return f"Thank you for registering! Please click on the link we emailed you ({form.email.data}) to validate your account!"
    return render_template('register.html', form=form, title='Register')

@auth_bp.route('/verify-email/<int:user_id>/<email_verification_code>')
def verify_email(user_id, email_verification_code):
    user = User.query.get(user_id)
    if user is None:
        return "Invalid Link: User not found"
    if datetime.fromisoformat(user.unverified_dispose_after) < datetime.utcnow():
        return "The link as expired. Please register again."
    if user.verified == True:
        return "User is already verified."

    if bcrypt.check_password_hash(user.link_code_hashed, email_verification_code):
        user.verified = True
        db.session.commit()
        return "The verification code has been accepted. Account has been verified."

@auth_bp.route('/resend-code', methods=['GET', 'POST'])
def resend_code():
    form = ResendCodeForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user is None:
            return render_template('resend_code.html', form=form, error="This email has not been registered.")
        if user.verified == True:
            return render_template('resend_code.html', form=form, error="This email has already been verified.")

        hashed_link_code_confirmation = send_confirmation_link(user)
        user.link_code_hashed = hashed_link_code_confirmation
        db.session.commit()
        return render_template('resend_code.html', form=form, error = "Success! Please review the email we sent you.")

    return render_template('resend_code.html', form=form)

@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))
