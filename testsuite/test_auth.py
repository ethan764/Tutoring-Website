from datetime import datetime, timedelta

import app.auth.routes as auth_routes
from app.models import User


def test_registration_saves_unverified_user_and_sends_verification(client, monkeypatch):
    token = "known-verification-token"
    monkeypatch.setattr(
        auth_routes,
        "send_confirmation_link",
        lambda user: auth_routes.bcrypt.generate_password_hash(token).decode("utf-8"),
    )

    response = client.post(
        "/auth/register",
        data={
            "email": "new-student@example.com",
            "password": "secret1",
            "confirm_password": "secret1",
            "submit": "Register",
        },
    )

    assert response.status_code == 302
    user = User.query.filter_by(email="new-student@example.com").one()
    assert user.verified is False
    assert user.link_code_hashed
    assert datetime.fromisoformat(user.unverified_dispose_after) > datetime.utcnow()


def test_registration_rejects_invalid_email_and_short_password(client):
    response = client.post(
        "/auth/register",
        data={
            "email": "not-an-email",
            "password": "short",
            "confirm_password": "short",
        },
    )
    assert response.status_code == 200
    assert User.query.count() == 0


def test_login_rejects_unknown_unverified_and_wrong_password(client, factories):
    factories.user(email="unverified@example.com", verified=False)
    factories.user(email="verified@example.com", verified=True)

    unknown = client.post(
        "/auth/login",
        data={"email": "missing@example.com", "password": "test-password"},
    )
    unverified = client.post(
        "/auth/login",
        data={"email": "unverified@example.com", "password": "test-password"},
    )
    wrong_password = client.post(
        "/auth/login",
        data={"email": "verified@example.com", "password": "wrong-password"},
    )

    assert b"No User Found" in unknown.data
    assert b"has not been verified" in unverified.data
    assert b"Invalid email or password" in wrong_password.data


def test_login_and_logout_for_verified_user(client, factories, login_as):
    factories.user(email="verified@example.com", verified=True)

    response = login_as(client, "verified@example.com")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/students/student_portal")

    response = client.get("/auth/logout")
    assert response.status_code == 302
    assert response.headers["Location"].endswith("/auth/login")


def test_verification_accepts_valid_token_and_rejects_invalid_token(client, factories, models):
    valid_token = "correct-token"
    user = factories.user(
        email="verify@example.com",
        verified=False,
        link_code_hashed=models.bcrypt.generate_password_hash(valid_token).decode("utf-8"),
        unverified_dispose_after=datetime.utcnow() + timedelta(hours=1),
    )

    invalid_response = client.get(f"/auth/verify-email/{user.id}/wrong-token")
    assert invalid_response.status_code == 302
    assert "Invalid%20verification%20code" in invalid_response.headers["Location"]
    assert User.query.get(user.id).verified is False

    valid_response = client.get(f"/auth/verify-email/{user.id}/{valid_token}")
    assert valid_response.status_code == 302
    assert User.query.get(user.id).verified is True


def test_verification_rejects_expired_or_missing_users(client, factories, models):
    expired_user = factories.user(
        email="expired@example.com",
        verified=False,
        link_code_hashed=models.bcrypt.generate_password_hash("token").decode("utf-8"),
        unverified_dispose_after=datetime.utcnow() - timedelta(hours=1),
    )

    expired = client.get(f"/auth/verify-email/{expired_user.id}/token")
    missing = client.get("/auth/verify-email/999/token")

    assert expired.status_code == 302
    assert "expired" in expired.headers["Location"].lower()
    assert User.query.get(expired_user.id).verified is False
    assert missing.status_code == 302
    assert "User%20not%20found" in missing.headers["Location"]


def test_resend_verification_rejects_unknown_and_verified_users(client, factories):
    factories.user(email="verified@example.com", verified=True)

    missing = client.post(
        "/auth/resend-code",
        data={"email": "missing@example.com"},
    )
    verified = client.post(
        "/auth/resend-code",
        data={"email": "verified@example.com"},
    )

    assert b"has not been registered" in missing.data
    assert b"already been verified" in verified.data


def test_resend_verification_replaces_token_for_unverified_user(client, factories, models, monkeypatch):
    token = "resent-token"
    user = factories.user(email="pending@example.com", verified=False)
    monkeypatch.setattr(
        auth_routes,
        "send_confirmation_link",
        lambda user: models.bcrypt.generate_password_hash(token).decode("utf-8"),
    )

    response = client.post(
        "/auth/resend-code",
        data={"email": "pending@example.com"},
    )

    assert response.status_code == 200
    assert b"Success" in response.data
    assert models.bcrypt.check_password_hash(User.query.get(user.id).link_code_hashed, token)
