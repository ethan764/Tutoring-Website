from datetime import date
from time import sleep

import pytest

import app.lessons.routes as lesson_routes
from app.extensions import db
from app.models import EmailPendingJob, Lesson, Student, TodoistLesson, User


def test_student_portal_shows_only_associated_students_lessons(client, factories, login_as):
    student = factories.student(name="Ada", meeting_link="meet.test")
    factories.lesson(student, lesson_date="2026-10-19", completed=False)
    factories.lesson(student, lesson_date="2026-10-12", completed=True, post_lesson_notes="Good work")
    other = factories.student(name="Grace")
    factories.lesson(other, lesson_date="2026-10-20", completed=False)
    factories.user(email="ada@example.com", student_id=student.id, verified=True)
    login_as(client, "ada@example.com")

    response = client.get("/students/student_portal")

    assert response.status_code == 200
    assert b"Hello Ada" in response.data
    assert b"2026-10-19" in response.data
    assert b"Good work" in response.data
    assert b"2026-10-20" not in response.data


def test_student_without_association_is_redirected_to_explanation(client, factories, login_as):
    factories.user(email="unassigned@example.com", verified=True)
    login_as(client, "unassigned@example.com")

    response = client.get("/students/student_portal")

    assert response.status_code == 302
    assert "/message/" in response.headers["Location"]


def test_admin_routes_require_login_and_allowlisted_email(client, factories, login_as, admin):
    student = factories.student()

    anonymous = client.get("/students/")
    assert anonymous.status_code == 302

    factories.user(email="ordinary@example.com", verified=True)
    login_as(client, "ordinary@example.com")
    forbidden = client.get("/students/")
    assert forbidden.status_code == 403

    client.get("/auth/logout")
    login_as(client, admin.email)
    allowed = client.get("/students/")
    assert allowed.status_code == 200
    assert student.name.encode() in allowed.data


def test_admin_can_add_student_with_empty_or_comma_separated_schedule(client, admin, login_as):
    login_as(client, admin.email)

    empty = client.post(
        "/students/add_student",
        data={"name": "No Schedule", "meeting_link": ""},
    )
    scheduled = client.post(
        "/students/add_student",
        data={"name": "Scheduled", "meeting_link": "meet.test", "schedule": "Mon 9AM, Tue 10AM"},
    )

    assert empty.status_code == scheduled.status_code == 302
    assert Student.query.filter_by(name="No Schedule").one().schedule == []
    assert Student.query.filter_by(name="Scheduled").one().schedule == ["Mon 9AM", "Tue 10AM"]


def test_admin_can_update_weekly_schedule(client, factories, admin, login_as):
    student = factories.student(schedule=["Mon 9AM"])
    login_as(client, admin.email)

    response = client.post(
        f"/students/update_schedule/{student.id}",
        data={"schedule": "Tue 10AM, Thu 2PM"},
    )

    assert response.status_code == 302
    assert student.schedule == ["Tue 10AM", "Thu 2PM"]


def test_admin_can_update_student_and_match_user_account(client, factories, admin, login_as):
    student = factories.student(name="Before", email="old@example.com", schedule=[])
    old_user = factories.user(email="old@example.com", student_id=student.id)
    matching_user = factories.user(email="new@example.com")
    login_as(client, admin.email)

    response = client.post(
        f"/students/update_student/{student.id}",
        data={
            "name": "After",
            "email": "new@example.com",
            "meeting_link": "meet.test",
            "schedule": "Wed 4PM",
            "general_notes": "Focus on geometry",
        },
    )

    assert response.status_code == 302
    assert student.name == "After"
    assert student.email == "new@example.com"
    assert student.schedule == ["Wed 4PM"]
    assert student.general_notes == "Focus on geometry"
    assert old_user.student_id is None
    assert matching_user.student_id == student.id


def test_student_chart_refreshes_scheduled_lesson_ids(client, factories, admin, login_as):
    student = factories.student(scheduled_lesson_ids=[])
    lesson = factories.lesson(student, completed=False)
    factories.lesson(student, completed=True)
    login_as(client, admin.email)

    response = client.get(f"/students/student_chart/{student.id}")

    assert response.status_code == 200
    assert student.scheduled_lesson_ids == [lesson.id]


@pytest.mark.parametrize(
    ("day", "expected"),
    [
        ("Monday", date(2026, 10, 19)),
        ("mon", date(2026, 10, 19)),
        ("M", date(2026, 10, 19)),
        ("TH", date(2026, 10, 22)),
        ("Sunday", date(2026, 10, 25)),
        ("su", date(2026, 10, 25)),
        ("MON", date(2026, 10, 19)),
    ],
)
def test_convert_day_week_year_to_date_accepts_documented_aliases(day, expected):
    assert lesson_routes.convert_day_week_year_to_date(day, 43, 2026) == expected


@pytest.mark.parametrize(
    ("week", "year", "day", "expected"),
    [
        (1, 2021, "Mon", date(2021, 1, 4)),
        (1, 2021, "Sun", date(2021, 1, 10)),
        (53, 2020, "Thu", date(2020, 12, 31)),
    ],
)
def test_convert_day_week_year_to_date_handles_iso_year_boundaries(week, year, day, expected):
    assert lesson_routes.convert_day_week_year_to_date(day, week, year) == expected


def test_convert_day_week_year_to_date_rejects_invalid_inputs():
    assert lesson_routes.convert_day_week_year_to_date("Funday", 43, 2026) is None
    assert lesson_routes.convert_day_week_year_to_date("Mon", 0, 2026) is None
    assert lesson_routes.convert_day_week_year_to_date("Mon", 54, 2026) is None


def test_weekly_schedule_creates_expected_lessons_and_skips_existing(client, factories, admin, login_as, monkeypatch):
    student = factories.student(name="Ada", schedule=["Mon 9AM", "Tue 10AM"])
    existing = factories.lesson(student, lesson_date="2026-10-19", scheduled_time_pst="8AM")
    add_calls, edit_calls = [], []
    monkeypatch.setattr(
        "app.models.add_lesson",
        lambda *args: (add_calls.append(args), type("Task", (), {"id": "scheduled-task"})())[1],
    )
    monkeypatch.setattr(
        "app.models.edit_lesson_date",
        lambda *args, **kwargs: edit_calls.append((args, kwargs)),
    )
    login_as(client, admin.email)

    for _ in range(2):
        response = client.post(
            "/lessons/reqs/create-lessons-from-weekly-schedule",
            data={"date_of_week": "2026-10-19"},
        )

    assert response.status_code == 302
    lessons = Lesson.query.filter_by(student_id=student.id).all()
    assert len(lessons) == 2
    assert existing.scheduled_time_pst == "9AM"
    assert next(lesson for lesson in lessons if lesson.lesson_date == "2026-10-20").scheduled_time_pst == "10AM"
    assert add_calls == [("Ada", "2026-10-20 10AM")]
    assert edit_calls == [
        (("scheduled-task", "2026-10-20 10AM"), {"completed": False})
    ]


def test_weekly_schedule_skips_blank_entries_and_requires_week_date(client, factories, admin, login_as, monkeypatch):
    student = factories.student(name="Blank", schedule=["", "   "])
    add_calls = []
    monkeypatch.setattr(
        Lesson,
        "create",
        classmethod(lambda cls, **kwargs: add_calls.append(kwargs)),
    )
    login_as(client, admin.email)

    missing_date = client.post("/lessons/reqs/create-lessons-from-weekly-schedule")
    valid_date = client.post(
        "/lessons/reqs/create-lessons-from-weekly-schedule",
        data={"date_of_week": "2026-10-19"},
    )

    assert missing_date.status_code == 400
    assert valid_date.status_code == 302
    assert student.schedule == ["", "   "]
    assert add_calls == []


def test_weekly_schedule_skips_invalid_day_entries(client, factories, admin, login_as, monkeypatch):
    student = factories.student(name="Invalid entries", schedule=["Funday 9AM", "Mon 9AM"])
    create_calls = []
    monkeypatch.setattr(
        Lesson,
        "create",
        classmethod(lambda cls, **kwargs: create_calls.append(kwargs)),
    )
    login_as(client, admin.email)

    response = client.post(
        "/lessons/reqs/create-lessons-from-weekly-schedule",
        data={"date_of_week": "2026-10-19"},
    )

    assert response.status_code == 302
    assert student.schedule == ["Funday 9AM", "Mon 9AM"]
    assert create_calls == [
        {
            "student_id": student.id,
            "student_name": student.name,
            "completed": False,
            "lesson_date": "2026-10-19",
            "scheduled_time_pst": "9AM",
        }
    ]


def test_task_manager_lists_students_and_unplanned_lessons(client, factories, admin, login_as):
    student = factories.student(name="Needs planning", schedule=["Mon 9AM"])
    unplanned = factories.lesson(
        student,
        lesson_date="2026-10-19",
        lesson_notes="",
        lesson_work="",
        completed=False,
    )
    factories.lesson(
        student,
        lesson_date="2026-10-20",
        lesson_notes="Ready",
        lesson_work="Chapter 2",
        completed=False,
    )
    login_as(client, admin.email)

    response = client.get("/lessons/task_manager")

    assert response.status_code == 200
    assert b"Needs planning" in response.data
    assert b"2026-10-19" in response.data
    assert b"2026-10-20" not in response.data


def test_lesson_model_creates_and_links_todoist_task(app, models, monkeypatch):
    calls = []

    def add_task(name, due):
        calls.append((name, due))
        return type("Task", (), {"id": "task-123"})()

    monkeypatch.setattr("app.models.add_lesson", add_task)
    with app.app_context():
        student = Student(name="Ada")
        db.session.add(student)
        db.session.commit()

        lesson = Lesson.create(
            student_id=student.id,
            student_name=student.name,
            lesson_date="2026-10-19",
            scheduled_time_pst="9AM",
        )

        mapping = TodoistLesson.query.filter_by(lesson_id=lesson.id).one()
        assert mapping.todoist_task_id == "task-123"
        assert calls == [("Ada", "2026-10-19 9AM")]


def test_lesson_model_skips_todoist_for_completed_or_explicitly_disabled_lessons(app, monkeypatch):
    calls = []
    monkeypatch.setattr("app.models.add_lesson", lambda *args: calls.append(args))
    with app.app_context():
        student = Student(name="Ada")
        db.session.add(student)
        db.session.commit()

        completed = Lesson.create(
            student_id=student.id,
            student_name=student.name,
            lesson_date="2026-10-19",
            completed=True,
        )
        imported = Lesson.create(
            create_todoist=False,
            student_id=student.id,
            student_name=student.name,
            lesson_date="2026-10-20",
            completed=False,
        )

        assert completed.id is not None
        assert imported.id is not None
        assert calls == []
        assert TodoistLesson.query.count() == 0


def test_lesson_and_todoist_link_timestamps_are_set_per_record(app):
    with app.app_context():
        student = Student(name="Ada")
        db.session.add(student)
        db.session.commit()
        first = Lesson(
            student_id=student.id,
            student_name=student.name,
            lesson_date="2026-10-19",
        )
        db.session.add(first)
        db.session.commit()
        sleep(0.01)
        second = TodoistLesson(lesson_id=first.id, todoist_task_id="task-123")
        db.session.add(second)
        db.session.commit()

        assert first.created_at is not None
        assert second.created_at is not None
        assert second.created_at > first.created_at


def test_lesson_edit_updates_existing_todoist_task(app, monkeypatch):
    edit_calls = []
    monkeypatch.setattr(
        "app.models.edit_lesson_date",
        lambda *args, **kwargs: edit_calls.append((args, kwargs)),
    )
    with app.app_context():
        student = Student(name="Ada")
        db.session.add(student)
        db.session.commit()
        lesson = Lesson(
            student_id=student.id,
            student_name=student.name,
            lesson_date="2026-10-19",
            scheduled_time_pst="9AM",
        )
        db.session.add(lesson)
        db.session.commit()
        db.session.add(TodoistLesson(lesson_id=lesson.id, todoist_task_id="task-123"))
        db.session.commit()

        updated = Lesson.edit(
            lesson.id,
            lesson_date="2026-10-20",
            scheduled_time_pst="10AM",
            completed=True,
        )

        assert updated.lesson_date == "2026-10-20"
        assert edit_calls == [
            (("task-123", "2026-10-20 10AM"), {"completed": True})
        ]


def test_record_lesson_updates_student_totals_and_sheets(client, factories, admin, login_as, monkeypatch):
    student = factories.student(scheduled_lesson_ids=[])
    lesson = factories.lesson(student, scheduled_time_pst="9AM")
    student.scheduled_lesson_ids = [lesson.id]
    db.session.commit()
    sheet_calls = []
    monkeypatch.setattr(lesson_routes, "record_lesson_info", lambda *args: sheet_calls.append(args))
    login_as(client, admin.email)

    response = client.post(
        f"/lessons/record_lesson/{student.id}",
        data={"lesson_id": str(lesson.id), "lesson_duration": "1", "post_lesson_notes": "Good progress"},
    )

    assert response.status_code == 302
    assert lesson.completed is True
    assert lesson.lesson_duration == 1
    assert lesson.post_lesson_notes == "Good progress"
    assert student.lessons_taken == 1
    assert student.scheduled_lesson_ids == []
    assert sheet_calls == [(student.name, lesson.lesson_date, "1", "Good progress")]


def test_lesson_planner_creates_and_edits_lessons(client, factories, admin, login_as, monkeypatch):
    student = factories.student(scheduled_lesson_ids=[])
    create_calls = []
    edit_calls = []
    original_create = Lesson.create
    original_edit = Lesson.edit

    def create_lesson(cls, **kwargs):
        create_calls.append(kwargs)
        return original_create(**kwargs)

    def edit_lesson(cls, lesson_id, **kwargs):
        edit_calls.append((lesson_id, kwargs))
        return original_edit(lesson_id, **kwargs)

    monkeypatch.setattr(Lesson, "create", classmethod(create_lesson))
    monkeypatch.setattr(Lesson, "edit", classmethod(edit_lesson))
    monkeypatch.setattr("app.models.add_lesson", lambda *args: type("Task", (), {"id": "planner-task"})())
    login_as(client, admin.email)

    created = client.post(
        f"/lessons/lesson_planner/{student.id}",
        data={
            "lesson_date": "2026-10-19",
            "lesson_homework": "Chapter 1",
            "lesson_notes": "Linear equations",
            "lesson_time": "9AM",
        },
    )
    lesson = Lesson.query.filter_by(student_id=student.id).one()
    edited = client.post(
        f"/lessons/lesson_planner/{student.id}/{lesson.id}",
        data={
            "lesson_date": "2026-10-20",
            "lesson_homework": "Chapter 2",
            "lesson_notes": "Inequalities",
            "lesson_time": "10AM",
        },
    )

    assert created.status_code == edited.status_code == 302
    assert create_calls[0]["lesson_date"] == "2026-10-19"
    assert student.scheduled_lesson_ids == [lesson.id]
    assert lesson.lesson_date == "2026-10-20"
    assert lesson.lesson_work == "Chapter 2"
    assert edit_calls[0][0] == lesson.id


def test_google_sheet_sync_creates_completed_lesson_without_todoist(client, factories, admin, login_as, monkeypatch):
    student = factories.student(name="Ada")
    monkeypatch.setattr(lesson_routes, "get_student_info", lambda: {})
    monkeypatch.setattr(
        lesson_routes,
        "get_lesson_info",
        lambda: {
            "Ada": {
                "2026-10-19": {
                    "lesson_date": "2026-10-19",
                    "lesson_duration": 1,
                    "post_lesson_notes": "Imported",
                }
            }
        },
    )
    todoist_calls = []
    monkeypatch.setattr("app.models.add_lesson", lambda *args: todoist_calls.append(args))
    login_as(client, admin.email)

    response = client.get("/lessons/reqs/sync-from-google-sheet")

    imported = next(
        lesson
        for lesson in Lesson.query.filter_by(student_id=student.id).all()
        if lesson.lesson_date == "2026-10-19"
    )
    assert response.status_code == 302
    assert imported.completed is True
    assert imported.post_lesson_notes == "Imported"
    assert todoist_calls == []
    assert TodoistLesson.query.filter_by(lesson_id=imported.id).first() is None


def test_google_sheet_sync_updates_existing_lesson_and_student_data(client, factories, admin, login_as, monkeypatch):
    student = factories.student(name="Ada", lessons_taken=0)
    existing = factories.lesson(
        student,
        lesson_date="2026-10-19",
        completed=False,
        post_lesson_notes="Old notes",
    )
    monkeypatch.setattr(
        lesson_routes,
        "get_student_info",
        lambda: {"Ada": {"lessons_taken": 4, "lessons_credited": 6}},
    )
    monkeypatch.setattr(
        lesson_routes,
        "get_lesson_info",
        lambda: {
            "Ada": {
                "2026-10-19": {
                    "lesson_date": "2026-10-19",
                    "lesson_duration": 1,
                    "post_lesson_notes": "Updated from sheet",
                }
            }
        },
    )
    login_as(client, admin.email)

    response = client.get("/lessons/reqs/sync-from-google-sheet")

    assert response.status_code == 302
    assert student.lessons_taken == 4
    assert student.lessons_credited == 6
    assert existing.completed is True
    assert existing.lesson_duration == 1
    assert existing.post_lesson_notes == "Updated from sheet"


def test_google_sheet_sync_ignores_unknown_students_and_is_idempotent(
    client, factories, admin, login_as, monkeypatch
):
    known_student = factories.student(name="Ada")
    monkeypatch.setattr(lesson_routes, "get_student_info", lambda: {"Unknown": {"lessons_taken": 3}})
    monkeypatch.setattr(
        lesson_routes,
        "get_lesson_info",
        lambda: {
            "Ada": {
                "2026-10-19": {
                    "lesson_date": "2026-10-19",
                    "lesson_duration": 1,
                    "post_lesson_notes": "Imported once",
                }
            },
            "Unknown": {
                "2026-10-20": {
                    "lesson_date": "2026-10-20",
                    "lesson_duration": 1,
                }
            },
        },
    )
    login_as(client, admin.email)

    first_sync = client.get("/lessons/reqs/sync-from-google-sheet")
    second_sync = client.get("/lessons/reqs/sync-from-google-sheet")

    imported = Lesson.query.filter_by(student_id=known_student.id).all()
    assert first_sync.status_code == second_sync.status_code == 302
    assert len(imported) == 1
    assert imported[0].completed is True
    assert imported[0].post_lesson_notes == "Imported once"
    assert Student.query.filter_by(name="Unknown").count() == 0


def test_lesson_suggestion_uses_student_lessons_and_notes(client, factories, admin, login_as, monkeypatch):
    student = factories.student(general_notes="Needs confidence with fractions")
    lesson = factories.lesson(student, lesson_notes="Fractions")
    calls = []
    monkeypatch.setattr(
        lesson_routes,
        "suggest_lessons_ollama",
        lambda previous, notes: calls.append((previous, notes)) or "Practice equivalent fractions",
    )
    login_as(client, admin.email)

    response = client.get(f"/lessons/reqs/lesson-suggestion/{student.id}")

    assert response.status_code == 200
    assert response.text == "Practice equivalent fractions"
    assert calls == [([lesson], student.general_notes)]


def test_courtesy_email_sends_one_personalized_email_per_student(client, factories, admin, login_as, monkeypatch):
    first = factories.student(name="Ada", email="ada@example.com")
    second = factories.student(name="Grace", email="grace@example.com")
    first_lesson = factories.lesson(first, lesson_date="2026-10-19", scheduled_time_pst="9AM")
    second_lesson = factories.lesson(second, lesson_date="2026-10-20", scheduled_time_pst="10AM")
    email_calls = []
    monkeypatch.setattr(lesson_routes, "send_email", lambda *args, **kwargs: email_calls.append((args, kwargs)))
    login_as(client, admin.email)

    response = client.post(
        "/lessons/reqs/send-courtesy-emails",
        data={
            "scheduled_lesson_ids": [str(first_lesson.id), str(second_lesson.id)],
            "subject_format": "Schedule",
            "body_format": "Hello _name_: _lsns_",
        },
    )

    assert response.status_code == 302
    assert len(email_calls) == 2
    assert {call[0][0] for call in email_calls} == {"ada@example.com", "grace@example.com"}
    assert all(call[1]["use_html"] is True for call in email_calls)


def test_courtesy_emails_can_schedule_one_persisted_job_per_lesson(
    client, factories, admin, login_as, monkeypatch
):
    student = factories.student(name="Ada", email="ada@example.com")
    first_lesson = factories.lesson(
        student,
        lesson_date="2026-10-20",
        scheduled_time_pst="9AM",
    )
    second_lesson = factories.lesson(
        student,
        lesson_date="2026-10-21",
        scheduled_time_pst="10AM",
    )
    scheduled_calls = []
    monkeypatch.setattr(
        lesson_routes.scheduler,
        "add_job",
        lambda **kwargs: scheduled_calls.append(kwargs),
    )
    login_as(client, admin.email)

    response = client.post(
        "/lessons/reqs/send-courtesy-emails",
        data={
            "send_day_before": "1",
            "scheduled_lesson_ids": [str(first_lesson.id), str(second_lesson.id)],
            "subject_format": "Schedule",
            "body_format": "Hello _name_: _lsns_",
        },
    )

    jobs = EmailPendingJob.query.order_by(EmailPendingJob.scheduled_time).all()
    assert response.status_code == 200
    assert [job.to_email for job in jobs] == ["ada@example.com", "ada@example.com"]
    assert [job.scheduled_time.isoformat() for job in jobs] == [
        "2026-10-19T16:00:00",
        "2026-10-20T16:00:00",
    ]
    assert all(job.subject == "Schedule" and job.use_html for job in jobs)
    assert "Hello Ada" in jobs[0].body
    assert "2026-10-20 at 9AM" in jobs[0].body
    assert [call["id"] for call in scheduled_calls] == [
        f"courtesy_email_{first_lesson.id}",
        f"courtesy_email_{second_lesson.id}",
    ]
    assert [call["run_date"] for call in scheduled_calls] == [
        jobs[0].scheduled_time,
        jobs[1].scheduled_time,
    ]
