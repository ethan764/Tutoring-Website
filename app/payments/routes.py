from flask import Blueprint, render_template, request, redirect, url_for, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models import Student, Lesson
from stripe_interactor import create_checkout_session, create_customer, find_subscriptions, cancel_subscriptions

from gsheet_interactor import get_payment_info

payments_by = Blueprint("payments", __name__)

@payments_by.route("/portal")
@login_required
def portal():
    student = Student.query.get(current_user.student_id)
    if student is None:
        abort(400, "No student found.")

    return render_template("payments.html", student=student)

    

@payments_by.route("/fetch_stripe/<student_id>/<price_type>", methods=["POST"])
@login_required
def fetch_stripe(student_id, price_type):
    # this type of auth should be a wrapper?
    if current_user.student_id != student_id:
        return redirect(url_for('static.message', message="Invalid Authentication."))

    student = Student.query.get(student_id)
    if student is None:
        return redirect(url_for('static.message', message="No student found."))

    customer_id = student.stripe_customer_id
    if not customer_id:
        customer = create_customer(student.name, student.email)
        student.stripe_customer_id = customer.id
        db.session.commit()
        customer_id = customer.id

    quantity = int(request.form.get('quantity', request.args.get('quantity', 1)))
    session = create_checkout_session(customer_id, price_type, quantity, url_for('payments.success', _external=True), url_for('payments.cancel', _external=True))
    return redirect(session.url)


@payments_by.route('/fetch-stripe-subscriptions')
@login_required
def fetch_pending_subscriptions():
    student = Student.query.get(current_user.student_id)
    if student is None:
        abort(400, description="No student found.")

    try:
        subscriptions = find_subscriptions()
        toReturn = []
        for subscription in subscriptions:
            toReturn.append({"???"}) #TODO TO DISPLAY ON ACTUAL PAGE
    except Exception as e:
        abort(500, description="Something went wrong on our end.")

@payments_by.route('/cancel-stripe-subscriptions')
@login_required
def cancel_subscriptions():
    student = Student.query.get(current_user.student_id)
    if student is None:
        return redirect(url_for('static.message', message="No Student Found."))

    try:
        cancel_subscriptions()
        return redirect(url_for('static.message', message="Success"))
    except Exception as e:
        return redirect(url_for('static.message', message=f"Please contact me directly. \n Error Occurred: {e}"))

@payments_by.route("/success")
@login_required
def success():
    return redirect(url_for('static.message', message="Payment successful! Thank you for your payment."))

@payments_by.route("/cancel")
@login_required
def cancel():
    return redirect(url_for('static.message', message="Payment canceled."))

@payments_by.route("/fetch-record")
@login_required
def fetch_record():
    student = Student.query.get(current_user.student_id)
    if student is None:
        abort(400, "No student found.")

    complete_record = get_payment_info()
    print(student.name)
    student_record = complete_record.get(student.name)
    print(student_record)

    return student_record