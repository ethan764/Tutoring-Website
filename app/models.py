from datetime import datetime, timedelta
from flask_login import UserMixin
from app.extensions import db

from todoist_interactor import add_lesson, edit_lesson_date

import asyncio


class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hashed = db.Column(db.String(150), nullable=False)
    link_code_hashed = db.Column(db.String(150), default='', nullable=False)
    verified = db.Column(db.Boolean, default=False)
    unverified_dispose_after = db.Column(db.Integer, default=datetime.utcnow() + timedelta(hours=24)) # treat this user as nonexistent after 24 hours

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_contact = db.Column(db.String(100), default='')
    email = db.Column(db.String(100), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lessons_taken = db.Column(db.Integer, default=0)
    lessons_credited = db.Column(db.Integer, default=0)
    scheduled_lesson_ids = db.Column(db.JSON, default=[])
    general_notes = db.Column(db.String(200), default='')
    schedule = db.Column(db.JSON, default=[]) # Store schedule as a JSON array of strings
    meeting_link = db.Column(db.String(200), nullable=True)
    stripe_customer_id = db.Column(db.String(100), nullable=True)

    def __repr__(self):
        return f'<Student {self.name}, {self.id}, Scheduled Lessons: {self.scheduled_lesson_ids}>'

class Lesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey('student.id'), nullable=False)
    student_name = db.Column(db.String(100), db.ForeignKey('student.name'), nullable=False)
    lesson_date = db.Column(db.JSON, nullable=False)
    lesson_notes = db.Column(db.String(100), default='')
    lesson_work = db.Column(db.String(100), default='')
    post_lesson_notes = db.Column(db.String(100), default='')
    completed = db.Column(db.Boolean, default=False)
    lesson_duration = db.Column(db.Integer, default = 0)  # Duration in hours
    created_at = db.Column(db.DateTime, default=datetime.utcnow())

    scheduled_time_pst = db.Column(db.String(50), default='')

    def __repr__(self):
        return f'<Lesson for Student ID {self.student_id}>'

    # create a lesson
    @classmethod
    def create(cls, **kwargs):
        lesson = cls(**kwargs)
        db.session.add(lesson)
        db.session.commit()

        if (lesson.completed):
            return lesson

        date_string = lesson.lesson_date + " " + lesson.scheduled_time_pst
        try:
            todoist_lesson = add_lesson(lesson.student_name, date_string)
            db.session.add(TodoistLesson(lesson_id=lesson.id, todoist_task_id=todoist_lesson.id))
            db.session.commit()
        except Exception as e:
            print(f"Failed to create Todoist lesson: {e}")

        return lesson

    @classmethod
    def edit(cls, lesson_id, **kwargs):
        lesson = cls.query.get(lesson_id)
        if not lesson:
            return None
        for key, value in kwargs.items():
            setattr(lesson, key, value)
        db.session.commit()

        # update Todoist lesson if lesson date or scheduled time has changed
        todoist_lesson = TodoistLesson.query.filter_by(lesson_id=lesson_id).first()
        if todoist_lesson:
            date_string = lesson.lesson_date + " " + lesson.scheduled_time_pst
            try:
                updated_todoist_lesson = edit_lesson_date(todoist_lesson.todoist_task_id, date_string, completed=lesson.completed)
                db.session.commit()
            except Exception as e:
                print(f"Failed to update Todoist lesson: {e}")

        return lesson
        

class TodoistLesson(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    lesson_id = db.Column(db.Integer, db.ForeignKey('lesson.id'), nullable=False)
    todoist_task_id = db.Column(db.String(100), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow())

    def __repr__(self):
        return f'<TodoistLesson for Lesson ID {self.lesson_id}, Todoist Task ID {self.todoist_task_id}>'
