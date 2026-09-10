from flask import Flask
from app.extensions import db, bcrypt, login_manager

def create_app():
    app = Flask(__name__)
    app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
    app.config['SECRET_KEY'] = 'secret_key'  # Replace with a secure key in production

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

    return app