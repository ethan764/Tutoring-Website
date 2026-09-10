from datetime import date, datetime

from flask import Blueprint, render_template, request, redirect, url_for
from sqlalchemy import and_, cast, String
from flask_login import login_required
import asyncio

from app.decorators import admin_whitelist_check
from app.extensions import db
from app.models import Student, Lesson
from gsheet_interactor import get_lesson_info, get_student_info, record_lesson_info
from lesson_suggestion import suggest_lessons_ollama
from email_interactor import send_email

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
        lesson_time = request.form.get('lesson_time')

        # Create a new Lesson object
        new_lesson = Lesson(
            student_id=student.id,
            student_name=student.name,
            lesson_date=lesson_date,
            lesson_notes=lesson_notes,
            lesson_work= lesson_homework,
            scheduled_time_pst=lesson_time,
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
        lesson.scheduled_time_pst = request.form.get('lesson_time')
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

def convert_day_week_year_to_date(day_of_week, week_of_year, year):
    days_of_week = {
        'monday': 1, "mon" : 1, "m" : 1,
        'tuesday': 2, "tue" : 2, "t" : 2,
        'wednesday': 3, "wed" : 3, "w" : 3,
        'thursday': 4, "thu" : 4, "th" : 4,
        'friday': 5, "fri" : 5, "f" : 5,
        'saturday': 6, "sat" : 6, "sa" : 6,
        'sunday': 7, "sun" : 7, "su" : 7
    }

    # validate inputs
    if not (day_of_week.lower() in days_of_week and 1 <= week_of_year <= 53 and year >= 1):
        return None  # Invalid day of the week

    return datetime.fromisocalendar(year, week_of_year, days_of_week[day_of_week.lower()]).date()

@lessons_bp.route('/reqs/create-lessons-from-weekly-schedule', methods=['POST'])
@login_required
@admin_whitelist_check
def create_lessons_from_weekly_schedule():
    date_of_week = request.form.get('date_of_week')
    if not date_of_week:
        return "Date of week is required", 400

    year, week_of_year, _ = datetime.fromisoformat(date_of_week).isocalendar()
    
    students = Student.query.filter(Student.schedule != []).all()

    for student in students:
        # scheduled_time is in format "(M/T/W/Th/F/Sa/Su) H(AM/PM)"; only date is necessary to extract from schedule, time is fine as string.
        for scheduled_time in student.schedule:
            day_of_week, informal_time = scheduled_time.split(' ', 1)
            lesson_date = convert_day_week_year_to_date(day_of_week, week_of_year, year)
            if lesson_date is None:
                continue  # Skip invalid entries

            # Check if a lesson already exists for this student and scheduled time
            lesson = Lesson.query.filter_by(student_id=student.id, scheduled_time_pst=scheduled_time).first()
            if lesson is None:
                lesson = Lesson(
                    student_id=student.id,
                    student_name=student.name,
                    completed=False
                )
                db.session.add(lesson)
            lesson.lesson_date = lesson_date
            lesson.scheduled_time_pst = informal_time

    db.session.commit()

    return redirect(url_for('students.index'))

@lessons_bp.route('/reqs/send-courtesy-emails', methods=['GET','POST'])
@login_required
@admin_whitelist_check
def send_courtesy_emails():

    if request.method == 'POST':
        scheduled_lesson_ids = request.form.getlist('scheduled_lesson_ids')
        subject = request.form.get('subject_format')
        body = request.form.get('body_format') # '_lsns_' means fill in lesson list; '_name_' means fill in name

        # iterates through all lessons, sorting by student
        student_to_lessons = {}
        while len(scheduled_lesson_ids) > 0:
            lesson = Lesson.query.get(scheduled_lesson_ids[0])
            if lesson != None:
                if lesson.student_id not in student_to_lessons:
                    student_to_lessons[lesson.student_id] = []

                student_to_lessons[lesson.student_id].append(lesson)

            scheduled_lesson_ids.pop(0)

        # emails by student
        for student_id, lessons in student_to_lessons.items():
            student = Student.query.get(student_id)
            if student == None:
                continue

            lesson_info_str = []
            for lesson in lessons:
                
                lesson_info_str.append(f'- Lesson on {lesson.lesson_date} at {lesson.scheduled_time_pst} (Pacific Time, PST)\n')
            lesson_info_str = "".join(lesson_info_str)

            body_exact = body.replace('_name_', student.name).replace('_lsns_', lesson_info_str)
            send_email(student.email, subject, body_exact, use_html=True)

        return "Success"
            

    scheduled_lessons = Lesson.query.filter_by(completed=False).order_by(Lesson.lesson_date).all()
    return render_template('email_send.html', scheduled_lessons=scheduled_lessons)