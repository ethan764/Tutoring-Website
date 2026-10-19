from types import SimpleNamespace

import app.payments.routes as payment_routes
import pytest


def test_public_pages_render(client):
    for path in ("/", "/about-me", "/policies", "/message/hello"):
        response = client.get(path)
        assert response.status_code == 200


def test_payment_portal_requires_associated_student(client, factories, login_as):
    unassigned = factories.user(email="unassigned@example.com", verified=True)
    login_as(client, unassigned.email)
    assert client.get("/payments/portal").status_code == 400

    student = factories.student(name="Ada")
    assigned = factories.user(
        email="ada@example.com",
        verified=True,
        student_id=student.id,
    )
    client.get("/auth/logout")
    login_as(client, assigned.email)
    response = client.get("/payments/portal")
    assert response.status_code == 200
    assert b"Set up autopay" in response.data


def test_checkout_rejects_other_students_and_invalid_student_ids(client, factories, login_as, monkeypatch):
    own_student = factories.student(name="Own")
    other_student = factories.student(name="Other")
    user = factories.user(email="ada@example.com", verified=True, student_id=own_student.id)
    login_as(client, user.email)
    checkout_calls = []
    monkeypatch.setattr(
        payment_routes,
        "create_checkout_session",
        lambda *args: checkout_calls.append(args) or SimpleNamespace(url="https://checkout.test/session"),
    )

    unauthorized = client.post(f"/payments/fetch_stripe/{other_student.id}/39%20weekly")
    malformed = client.post("/payments/fetch_stripe/not-an-id/39%20weekly")

    assert unauthorized.status_code == 403
    assert malformed.status_code == 404
    assert checkout_calls == []


def test_checkout_creates_customer_and_redirects(client, factories, login_as, monkeypatch):
    student = factories.student(name="Ada", email="ada@example.com")
    user = factories.user(email="ada@example.com", verified=True, student_id=student.id)
    login_as(client, user.email)
    customer_calls = []
    checkout_calls = []
    monkeypatch.setattr(
        payment_routes,
        "create_customer",
        lambda *args: customer_calls.append(args) or SimpleNamespace(id="cus-123"),
    )
    monkeypatch.setattr(
        payment_routes,
        "create_checkout_session",
        lambda *args: checkout_calls.append(args) or SimpleNamespace(url="https://checkout.test/session"),
    )

    response = client.post(
        f"/payments/fetch_stripe/{student.id}/39%20weekly",
        data={"quantity": "3"},
    )

    assert response.status_code == 302
    assert response.headers["Location"] == "https://checkout.test/session"
    assert customer_calls == [("Ada", "ada@example.com")]
    assert student.stripe_customer_id == "cus-123"
    assert checkout_calls[0][0:3] == ("cus-123", "39 weekly", 3)


def test_checkout_accepts_maximum_quantity(client, factories, login_as, monkeypatch):
    student = factories.student(name="Ada", email="ada@example.com")
    user = factories.user(email="ada@example.com", verified=True, student_id=student.id)
    login_as(client, user.email)
    checkout_calls = []
    monkeypatch.setattr(
        payment_routes,
        "create_checkout_session",
        lambda *args: checkout_calls.append(args) or SimpleNamespace(url="https://checkout.test/session"),
    )

    response = client.post(
        f"/payments/fetch_stripe/{student.id}/39%20weekly",
        data={"quantity": "100"},
    )

    assert response.status_code == 302
    assert checkout_calls[0][2] == 100


def test_checkout_reuses_existing_stripe_customer(client, factories, login_as, monkeypatch):
    student = factories.student(stripe_customer_id="cus-existing")
    user = factories.user(email="ada@example.com", verified=True, student_id=student.id)
    login_as(client, user.email)
    create_customer = []
    checkout_calls = []
    monkeypatch.setattr(payment_routes, "create_customer", lambda *args: create_customer.append(args))
    monkeypatch.setattr(
        payment_routes,
        "create_checkout_session",
        lambda *args: checkout_calls.append(args) or SimpleNamespace(url="https://checkout.test/reused"),
    )

    response = client.post(f"/payments/fetch_stripe/{student.id}/39%20weekly")

    assert response.status_code == 302
    assert create_customer == []
    assert checkout_calls[0][0] == "cus-existing"
    assert checkout_calls[0][2] == 1


@pytest.mark.parametrize("quantity", ["not-a-number", "1.5", "0", "-1", "101"])
def test_checkout_rejects_invalid_quantities_before_stripe_calls(
    client, factories, login_as, monkeypatch, quantity
):
    student = factories.student(name="Ada", email="ada@example.com")
    user = factories.user(email="ada@example.com", verified=True, student_id=student.id)
    login_as(client, user.email)
    stripe_calls = []
    monkeypatch.setattr(
        payment_routes,
        "create_customer",
        lambda *args: stripe_calls.append(("customer", args)),
    )
    monkeypatch.setattr(
        payment_routes,
        "create_checkout_session",
        lambda *args: stripe_calls.append(("checkout", args)),
    )

    response = client.post(
        f"/payments/fetch_stripe/{student.id}/39%20weekly",
        data={"quantity": quantity},
    )

    assert response.status_code == 400
    assert stripe_calls == []
    assert student.stripe_customer_id is None


def test_checkout_rejects_unsupported_price_before_stripe_calls(client, factories, login_as, monkeypatch):
    student = factories.student(name="Ada", email="ada@example.com")
    user = factories.user(email="ada@example.com", verified=True, student_id=student.id)
    login_as(client, user.email)
    stripe_calls = []
    monkeypatch.setattr(
        payment_routes,
        "create_customer",
        lambda *args: stripe_calls.append(("customer", args)),
    )
    monkeypatch.setattr(
        payment_routes,
        "create_checkout_session",
        lambda *args: stripe_calls.append(("checkout", args)),
    )

    response = client.post(f"/payments/fetch_stripe/{student.id}/invalid-price")

    assert response.status_code == 400
    assert stripe_calls == []
    assert student.stripe_customer_id is None


def test_subscription_list_and_cancellation_delegate_to_stripe(client, factories, login_as, monkeypatch):
    student = factories.student(stripe_customer_id="cus-123")
    user = factories.user(email="ada@example.com", verified=True, student_id=student.id)
    login_as(client, user.email)
    find_calls = []
    cancel_calls = []
    monkeypatch.setattr(
        payment_routes,
        "find_subscriptions",
        lambda customer_id: find_calls.append(customer_id) or [object(), object()],
    )
    monkeypatch.setattr(
        payment_routes,
        "cancel_subscriptions_direct",
        lambda customer_id: cancel_calls.append(customer_id),
    )

    subscriptions = client.get("/payments/fetch-stripe-subscriptions")
    canceled = client.get("/payments/cancel-stripe-subscriptions")

    assert subscriptions.status_code == 200
    assert subscriptions.json == ["You have auto-pay set up for 2 lessons."]
    assert find_calls == ["cus-123"]
    assert canceled.status_code == 302
    assert cancel_calls == ["cus-123"]


def test_subscription_lookup_reports_service_failure(client, factories, login_as, monkeypatch):
    student = factories.student(stripe_customer_id="cus-123")
    user = factories.user(email="ada@example.com", verified=True, student_id=student.id)
    login_as(client, user.email)
    monkeypatch.setattr(
        payment_routes,
        "find_subscriptions",
        lambda customer_id: (_ for _ in ()).throw(RuntimeError("Stripe unavailable")),
    )

    response = client.get("/payments/fetch-stripe-subscriptions")

    assert response.status_code == 500


def test_fetch_payment_history_returns_students_entries(client, factories, login_as, monkeypatch):
    student = factories.student(name="Ada")
    user = factories.user(email="ada@example.com", verified=True, student_id=student.id)
    login_as(client, user.email)
    monkeypatch.setattr(
        payment_routes,
        "get_payment_info",
        lambda: {"Ada": [{"Timestamp": "2026-10-01", "Sum of Payment": 39}]},
    )

    response = client.get("/payments/fetch-record")

    assert response.status_code == 200
    assert response.json == [{"Timestamp": "2026-10-01", "Sum of Payment": 39}]


def test_payment_webhook_returns_success_or_error_status(client, monkeypatch):
    monkeypatch.setattr(payment_routes, "on_payment_success", lambda request: True)
    success = client.post("/payments/recieve-payments", data=b"success")

    monkeypatch.setattr(payment_routes, "on_payment_success", lambda request: "invalid signature")
    rejected = client.post("/payments/recieve-payments", data=b"failure")

    assert success.status_code == 200
    assert success.json == {"success": True}
    assert rejected.status_code == 400
    assert rejected.json == {"error": "invalid signature"}


def test_payment_success_and_cancel_pages_require_login(client, factories, login_as):
    user = factories.user(email="ada@example.com", verified=True)

    assert client.get("/payments/success").status_code == 302
    login_as(client, user.email)
    success = client.get("/payments/success")
    canceled = client.get("/payments/cancel")

    assert success.status_code == 302
    assert "Payment%20successful" in success.headers["Location"]
    assert canceled.status_code == 302
    assert "Payment%20canceled" in canceled.headers["Location"]
