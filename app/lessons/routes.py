from flask import Blueprint, render_template, request, redirect, url_for
from sqlalchemy import and_, cast, String
from flask_login import login_required
import asyncio

from app.decorators import admin_whitelist_check
from app.extensions import db
from app.models import Student, Lesson
from gsheet_interactor import get_lesson_info, get_student_info, record_lesson_info
from lesson_suggestion import suggest_lessons_ollama

lessons_bp = Blueprint("lessons", __name__)


@lessons_bp.route('/record_lesson/<int:student_id>', methods=['POST'])
@login_required
@admin_whitelist_check
def record_lesson(student_id):
    student = Student.query.get_or_404(student_id)
    lesson_id = request.form.get('lesson_id')
    lesson_duration = request.form.get('lesson_duration')
    post_lesson_notes = request.form.get('post_lesson_notes')

    lesson = Lesson.query.get_or_404(lesson_id)
    lesson.lesson_duration = int(lesson_duration)
    lesson.post_lesson_notes = post_lesson_notes
    lesson.completed = True

    student.lessons_taken += lesson.lesson_duration #counts hours
    if lesson.id in student.scheduled_lesson_ids:
        student.scheduled_lesson_ids = [lid for lid in student.scheduled_lesson_ids if lid != lesson.id]  # Remove the lesson ID from scheduled lessons

    db.session.commit()

    async def record_gsheet():
        record_lesson_info(student.name, lesson.lesson_date, lesson_duration, post_lesson_notes)
    asyncio.run(record_gsheet())

    return redirect(url_for('students.student_chart', student_id=student.id))

@lessons_bp.route('/lesson_planner/<int:student_id>', methods=['GET', 'POST'])
@login_required
@admin_whitelist_check
def lesson_planner_create_lesson(student_id):
    student = Student.query.get_or_404(student_id)
    if request.method == 'POST':
        # Handle form submission
        lesson_date = request.form.get('lesson_date')
        lesson_homework = request.form.get('lesson_homework')
        lesson_notes = request.form.get('lesson_notes')

        # Create a new Lesson object
        new_lesson = Lesson(
            student_id=student.id,
            student_name=student.name,
            lesson_date=lesson_date,
            lesson_notes=lesson_notes,
            lesson_work= lesson_homework,
            completed=False
        )
        db.session.add(new_lesson)

        # Update the student's scheduled lessons
        student.scheduled_lesson_ids = student.scheduled_lesson_ids + [new_lesson.id]
        db.session.commit()

        return redirect(url_for('lessons.task_manager', student_id=student.id))

    return render_template('lesson planner.html', student=student, lesson=None, previous_lessons=Lesson.query.filter_by(student_id=student.id).order_by(Lesson.lesson_date.desc()).all())

@lessons_bp.route('/lesson_planner/<int:student_id>/<int:lesson_id>', methods=['GET', 'POST'])
@login_required
@admin_whitelist_check
def lesson_planner_edit_lesson(student_id, lesson_id):
    student = Student.query.get_or_404(student_id)
    lesson = Lesson.query.get_or_404(lesson_id)
    print(lesson.lesson_date)

    if request.method == 'POST':
        # Handle form submission for editing the lesson
        lesson.lesson_date = request.form.get('lesson_date')
        lesson.lesson_notes = request.form.get('lesson_notes')
        lesson.lesson_work = request.form.get('lesson_homework')
        db.session.commit()

        return redirect(url_for('students.student_chart', student_id=student.id))

    return render_template('lesson planner.html', student=student, lesson=lesson, previous_lessons=Lesson.query.filter_by(student_id=student.id).order_by(Lesson.lesson_date.desc()).all())


@lessons_bp.route('/task_manager')
@login_required
@admin_whitelist_check
def task_manager():
    students = Student.query.filter(Student.schedule != []).all()

    unplanned_lessons = Lesson.query.filter_by(lesson_notes='', lesson_work='', completed=False).order_by(Lesson.lesson_date).all()

    # Sort students by the number of scheduled lessons in descending order
    students.sort(key=lambda s: len(s.scheduled_lesson_ids), reverse=False)
    print(students)

    return render_template('task manager.html', students=students, unplanned_lessons=unplanned_lessons)

@lessons_bp.route('/reqs/lesson-suggestion/<int:student_id>')
@login_required
@admin_whitelist_check
def suggest_lesson(student_id):
    student = Student.query.get_or_404(student_id)
    previous_lessons=Lesson.query.filter_by(student_id=student.id).order_by(Lesson.lesson_date.desc()).all()
    suggestion = suggest_lessons_ollama(previous_lessons, student.general_notes)
    return suggestion



@lessons_bp.route('/reqs/sync-from-google-sheet')
@login_required
@admin_whitelist_check
def sync_from_google_sheet():
    lessons = Lesson.query.all()

    # update student info
    students_gsheet = get_student_info()
    for name, info in students_gsheet.items():
        student = Student.query.filter_by(name=name).first()
        if student == None:
            continue

        for entry, data in info.items():
            #assumes that entry is a member of class Student; and that gsheets is most updated
            setattr(student, entry, data)

    #update lesson info
    lessons_gsheet = get_lesson_info()
    for name, lesson_dict in lessons_gsheet.items():
        student = Student.query.filter_by(name=name).first()        
        if student == None:
            continue


        for date, info in lesson_dict.items():
            existing = Lesson.query.filter(and_(Lesson.student_name==name, cast(Lesson.lesson_date, String)==f'"{date}"')).first()
            if existing == None:
                existing = Lesson(
                    student_id=student.id,
                    student_name=student.name,
                    lesson_date=date,
                    completed=True
                )

                db.session.add(existing)

            for entry, data in info.items():
                setattr(existing, entry, data)

    db.session.commit()

    return redirect(url_for('students.index'))
