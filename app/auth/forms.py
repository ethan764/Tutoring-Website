from flask_wtf import FlaskForm
from app.extensions import db
from email_interactor import val_email
from wtforms import PasswordField, SubmitField, StringField
from datetime import datetime
from wtforms.validators import (
    DataRequired,
    Email,
    Length,
    ValidationError,
    EqualTo
)

from app.models import User


class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(message='Please enter a valid email address.'), Length(min=6, max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    confirm_password = PasswordField('Confirm Password', validators=[DataRequired(),  EqualTo('password')])
    submit = SubmitField('Register')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()

        executed, status = val_email(email.data)

        if executed == False or status == False:
            raise ValidationError("Your email isn't valid. Please enter a valid email.")

        if user:
            if user.verified == False and datetime.fromisoformat(user.unverified_dispose_after) < datetime.utcnow():
                db.session.delete(user)
                db.session.commit()
                return
            # TODO: ADD RESEND CODE FUNC.

            raise ValidationError('Email is already registered. Please choose a different one.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(message='Please enter a valid email address.'), Length(min=6, max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    submit = SubmitField('Login')

class ResendCodeForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(message='Please enter a valid email address.'), Length(min=6, max=100)])
    submit = SubmitField('Resend Code')