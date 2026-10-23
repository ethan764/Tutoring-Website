import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email_validator import validate_email, EmailNotValidError



# validates emails, expect bool verification, normalized email.
def val_email(to_email):
    try:
        # Validate and get normalized form
        valid = validate_email(str(to_email))
        return True, valid.normalized
    except EmailNotValidError as e:
        return False, str(e)

# Sends an email using Gmail's SMTP server. validates email, requires subject and body.
def send_email(to_email, subject, body, use_html=False):
    if val_email(to_email) == False:
        print("Invalid email: " + to_email)
        return
    
    from_email = 'ethan.nguyen.tutoring@gmail.com'
    email_password = os.environ.get('GMAIL_TUTORING_APP_PASSWORD')

    msg = MIMEMultipart()
    msg['From'] = from_email
    msg['To'] = to_email
    msg['Subject'] = subject

    msg.attach(MIMEText(body, 'html' if use_html == True else 'plain'))
    print("test")
    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(from_email, email_password)
            server.sendmail(from_email, to_email, msg.as_string())
            print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email to {to_email}: {e}")

def send_scheduled_email(to_email, subject, body, use_html, job_id):
    #delete the job from the database after sending the email
    from app.models import EmailPendingJob
    from flask import current_app
    app = current_app._get_current_object()

    with app.app_context():
        send_email(to_email, subject, body, use_html)
        job = EmailPendingJob.query.get(job_id)
        if job:
            from app.extensions import db
            db.session.delete(job)
            db.session.commit()

    #send email
    print("Sending scheduled email to:", to_email, "with subject:", subject)
    send_email(to_email, subject, body, use_html)
