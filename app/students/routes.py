from flask import Blueprint, render_template, request, redirect, url_for
from flask_login import login_required

from app.decorators import admin_whitelist_check
from app.extensions import db
from app.models import Student, Lesson


students_bp = Blueprint("students", __name__)


@students_bp.route('/')
@login_required
@admin_whitelist_check
def index():
    students = Student.query.all() #todo order by soonest lesson
    return render_template('students.html', students=students)

@students_bp.route('/update_schedule/<int:student_id>', methods=['POST'])
@login_required
@admin_whitelist_check
def update_schedule(student_id):
    student = Student.query.get_or_404(student_id)
    student.schedule = request.form.get('schedule').split(', ')
    db.session.commit()
    return redirect(url_for('students.index'))

@students_bp.route('/update_student/<int:student_id>', methods=['POST'])
@login_required
@admin_whitelist_check
def update_student(student_id):
    student = Student.query.get_or_404(student_id)
    student.name = request.form.get('name')
    student.meeting_link = request.form.get('meeting_link')
    student.schedule = request.form.get('schedule').split(', ')
    student.general_notes = request.form.get('general_notes')
    db.session.commit()
    return redirect(url_for('students.student_chart', student_id=student.id))

@students_bp.route('/add_student', methods=['POST'])
@login_required
@admin_whitelist_check
def add_student():
    name = request.form.get('name')
    meeting_link = request.form.get('meeting_link')
    schedule = request.form.get('schedule').split(', ')

    new_student = Student(name=name, meeting_link=meeting_link, schedule=schedule)
    db.session.add(new_student)
    db.session.commit()

    return redirect(url_for('students.index'))

@students_bp.route('/student_chart/<int:student_id>')
@login_required
@admin_whitelist_check
def student_chart(student_id):

    student = Student.query.get_or_404(student_id)

    
    # Update database scheduled id's to match the actual scheduled lessons for the student
    student.scheduled_lesson_ids = [lesson.id for lesson in Lesson.query.filter_by(student_id=student.id, completed=False).all()]
    db.session.commit()

    student_scheduled_lessons = Lesson.query.filter_by(student_id=student.id, completed=False).all()
    student_past_lessons = Lesson.query.filter_by(student_id=student.id, completed=True).order_by(Lesson.lesson_date.desc()).all()
    return render_template('student_chart.html', student=student, scheduled_lessons=student_scheduled_lessons, past_lessons=student_past_lessons)
