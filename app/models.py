from datetime import datetime, timedelta
from flask_login import UserMixin
from app.extensions import db


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
