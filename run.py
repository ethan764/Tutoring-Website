from flask_apscheduler import scheduler

from app import create_app

app = create_app()


if __name__ == '__main__':
    app.run(debug=True)
    
    from email_interactor import send_scheduled_email
    from app.models import EmailPendingJob
    with app.app_context():
        for job in EmailPendingJob.query.all():
            scheduler.add_job(
                id=str(job.id),
                func=send_scheduled_email,
                trigger='date',
                run_date=job.scheduled_time,
                misfire_grace_time=3600,  # 1 hour grace period
                args=[job.to_email, job.subject, job.body, job.use_html, job.id]
            )