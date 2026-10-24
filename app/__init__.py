from flask import Flask
from app.extensions import db, bcrypt, login_manager, scheduler
from apscheduler.events import EVENT_JOB_MISSED

class Config:
    SCHEDULER_API_ENABLED = True
    SCHEDULER_ENABLED = True

def create_app(config=None):
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
    app.config['SECRET_KEY'] = 'secret_key'  # Replace with a secure key in production
    app.config.from_object(Config)
    if config:
        app.config.update(config)

    db.init_app(app)
    bcrypt.init_app(app)

    login_manager.init_app(app)
    login_manager.login_view = 'auth.login'

    from app.models import User
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    from app.auth.routes import auth_bp
    from app.students.routes import students_bp
    from app.lessons.routes import lessons_bp
    from app.payments.routes import payments_by
    from app.static.routes import static_bp

    app.register_blueprint(auth_bp, url_prefix='/auth')
    app.register_blueprint(students_bp, url_prefix='/students')
    app.register_blueprint(lessons_bp, url_prefix='/lessons')
    app.register_blueprint(payments_by, url_prefix='/payments')
    app.register_blueprint(static_bp, url_prefix="/")

    if app.config["SCHEDULER_ENABLED"]:
        scheduler.init_app(app)
        from app.models import EmailPendingJob
        from email_interactor import send_scheduled_email

        with app.app_context():
            def delete_job(event):
                with app.app_context():
                    job_id = event.job_id
                    job = EmailPendingJob.query.get(job_id)
                    if job:
                        db.session.delete(job)
                        db.session.commit()
            scheduler.add_listener(delete_job, EVENT_JOB_MISSED)

            for job in EmailPendingJob.query.all():
                scheduler.add_job(
                    id=str(job.id),
                    func=send_scheduled_email,
                    trigger='date',
                    run_date=job.scheduled_time,
                    misfire_grace_time=3600,
                    args=[job.to_email, job.subject, job.body, job.use_html, job.id],
                    replace_existing=True,
                )

        scheduler.start()

    return app