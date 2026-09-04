from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required

from app.extensions import db
from app.models import Student, Lesson
from stripe_interactor import create_checkout_session, create_customer

payments_by = Blueprint("payments", __name__)

@payments_by.route("/payments/fetch_stripe/<student_id>/<price_type>", methods=["GET"])
@login_required
def fetch_stripe(student_id, price_type):
    student = Student.query.get_or_404(student_id)

    customer_id = student.stripe_customer_id
    if not customer_id:
        customer = create_customer(student.name, student.email)
        student.stripe_customer_id = customer.id
        db.session.commit()
        customer_id = customer.id

    session = create_checkout_session(customer_id, price_type, int(request.args.get('quantity', 1)), url_for('payments.success', _external=True), url_for('payments.cancel', _external=True))
    return redirect(session.url)

@payments_by.route("/payments/success")
@login_required
def success():
    return "Payment successful! Thank you for your payment." # create html later

@payments_by.route("/payments/cancel")
@login_required
def cancel():
    return "Payment canceled. Please try again." # create html later
