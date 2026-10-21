import sys
import types
from types import SimpleNamespace

import pytest


def install_service_stubs():
    todoist = types.ModuleType("todoist_interactor")
    todoist.add_lesson = lambda *args, **kwargs: SimpleNamespace(id="todoist-task")
    todoist.edit_lesson_date = lambda *args, **kwargs: None
    sys.modules["todoist_interactor"] = todoist

    sheets = types.ModuleType("gsheet_interactor")
    sheets.get_lesson_info = lambda: {}
    sheets.get_student_info = lambda: {}
    sheets.record_lesson_info = lambda *args, **kwargs: None
    sheets.get_payment_info = lambda: {}
    sheets.record_payment_info = lambda *args, **kwargs: None
    sys.modules["gsheet_interactor"] = sheets

    email = types.ModuleType("email_interactor")
    email.send_email = lambda *args, **kwargs: None
    email.send_scheduled_email = lambda *args, **kwargs: None
    email.val_email = lambda address: (True, address)
    sys.modules["email_interactor"] = email

    suggestions = types.ModuleType("lesson_suggestion")
    suggestions.suggest_lessons_ollama = lambda *args, **kwargs: "Suggested homework"
    sys.modules["lesson_suggestion"] = suggestions

    stripe = types.ModuleType("stripe_interactor")
    stripe.create_checkout_session = lambda *args, **kwargs: SimpleNamespace(url="https://checkout.test/session")
    stripe.create_customer = lambda *args, **kwargs: SimpleNamespace(id="stripe-customer")
    stripe.find_subscriptions = lambda *args, **kwargs: []
    stripe.cancel_subscriptions = lambda *args, **kwargs: None
    stripe.on_payment_success = lambda *args, **kwargs: True
    stripe.price_id_dict = {
        "39 one-time": "test-price-one-time",
        "39 weekly": "test-price-weekly",
        "35 one-time": "test-price-discount-one-time",
        "35 weekly": "test-price-discount-weekly",
    }
    sys.modules["stripe_interactor"] = stripe


install_service_stubs()

from app import create_app
from app.extensions import bcrypt, db
from app.models import Lesson, Student, TodoistLesson, User


@pytest.fixture
def app():
    app = create_app(
        {
            "TESTING": True,
            "SQLALCHEMY_DATABASE_URI": "sqlite://",
            "SECRET_KEY": "test-secret",
            "WTF_CSRF_ENABLED": False,
            "SCHEDULER_ENABLED": False,
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def app_context(app):
    with app.app_context():
        yield


@pytest.fixture
def client(app_context, app):
    return app.test_client()


@pytest.fixture
def models():
    return SimpleNamespace(
        bcrypt=bcrypt,
        db=db,
        Lesson=Lesson,
        Student=Student,
        TodoistLesson=TodoistLesson,
        User=User,
    )


@pytest.fixture
def factories(app_context, models):
    def make_student(name="Student", **kwargs):
        student = models.Student(name=name, **kwargs)
        models.db.session.add(student)
        models.db.session.commit()
        return student

    def make_user(email="student@example.com", password="test-password", **kwargs):
        user = models.User(
            email=email,
            password_hashed=models.bcrypt.generate_password_hash(password).decode("utf-8"),
            verified=kwargs.pop("verified", True),
            **kwargs,
        )
        models.db.session.add(user)
        models.db.session.commit()
        return user

    def make_lesson(student, lesson_date="2026-10-19", **kwargs):
        lesson = models.Lesson(
            student_id=student.id,
            student_name=student.name,
            lesson_date=lesson_date,
            **kwargs,
        )
        models.db.session.add(lesson)
        models.db.session.commit()
        return lesson

    return SimpleNamespace(student=make_student, user=make_user, lesson=make_lesson)


def login(client, email, password="test-password"):
    return client.post(
        "/auth/login",
        data={"email": email, "password": password, "submit": "Login"},
        follow_redirects=False,
    )


@pytest.fixture
def login_as():
    return login


@pytest.fixture
def admin(factories):
    return factories.user(email="ethannguyen764@gmail.com")
