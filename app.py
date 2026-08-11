from flask import Flask, redirect, render_template, request, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
db = SQLAlchemy(app)

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    parent_contact = db.Column(db.String(100), default='')
    student_contact = db.Column(db.String(100), default='')
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    lessons_taken = db.Column(db.Integer, default=0)
    lessons_credited = db.Column(db.Integer, default=0)
    scheduled_lesson_ids = db.Column(db.JSON, default=[])
    general_notes = db.Column(db.String(200), default='')
    schedule = db.Column(db.JSON, default=[]) # Store schedule as a JSON array of strings
    meeting_link = db.Column(db.String(200), nullable=True)

    def __repr__(self):
        return f'<Student {self.name}, {self.id}>'

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Lesson for Student ID {self.student_id}>'

@app.route('/')
def index():
    students = Student.query.all() #todo order by soonest lesson
    return render_template('students.html', students=students)

@app.route('/update_schedule/<int:student_id>', methods=['POST'])
def update_schedule(student_id):
    student = Student.query.get_or_404(student_id)
    student.schedule = request.form.get('schedule').split(', ')
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/update_student/<int:student_id>', methods=['POST'])
def update_student(student_id):
    student = Student.query.get_or_404(student_id)
    student.name = request.form.get('name')
    student.meeting_link = request.form.get('meeting_link')
    student.schedule = request.form.get('schedule').split(', ')
    student.general_notes = request.form.get('general_notes')
    db.session.commit()
    return redirect(url_for('student_chart', student_id=student.id))

@app.route('/add_student', methods=['POST'])
def add_student():
    name = request.form.get('name')
    meeting_link = request.form.get('meeting_link')
    schedule = request.form.get('schedule').split(', ')

    new_student = Student(name=name, meeting_link=meeting_link, schedule=schedule)
    db.session.add(new_student)
    db.session.commit()

    return redirect(url_for('index'))

@app.route('/student_chart/<int:student_id>')
def student_chart(student_id):
    student = Student.query.get_or_404(student_id)
    student_scheduled_lessons = Lesson.query.filter_by(student_id=student.id, completed=False).all()
    student_past_lessons = Lesson.query.filter_by(student_id=student.id, completed=True).all()
    return render_template('student_chart.html', student=student, scheduled_lessons=student_scheduled_lessons, past_lessons=student_past_lessons)


@app.route('/record_lesson/<int:student_id>', methods=['POST'])
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
        student.scheduled_lesson_ids.remove(lesson.id)

    db.session.commit()

    return redirect(url_for('student_chart', student_id=student.id))

@app.route('/lesson_planner/<int:student_id>', methods=['GET', 'POST'])
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
        student.scheduled_lesson_ids.append(new_lesson.id)
        db.session.commit()

        return redirect(url_for('task_manager', student_id=student.id))

    return render_template('lesson planner.html', student=student, lesson=None, previous_lessons=Lesson.query.filter_by(student_id=student.id).order_by(Lesson.lesson_date.desc()).all())

@app.route('/lesson_planner/<int:student_id>/<int:lesson_id>', methods=['GET', 'POST'])
def lesson_planner_edit_lesson(student_id, lesson_id):
    student = Student.query.get_or_404(student_id)
    lesson = Lesson.query.get_or_404(lesson_id)

    if request.method == 'POST':
        # Handle form submission for editing the lesson
        lesson.lesson_date = request.form.get('lesson_date')
        lesson.lesson_notes = request.form.get('lesson_notes')
        lesson.lesson_work = request.form.get('lesson_homework')
        db.session.commit()

        return redirect(url_for('task_manager', student_id=student.id))

    return render_template('lesson planner.html', student=student, lesson=lesson, previous_lessons=Lesson.query.filter_by(student_id=student.id).order_by(Lesson.lesson_date.desc()).all())


@app.route('/task_manager')
def task_manager():
    students = Student.query.filter(Student.schedule != []).all()

    unplanned_lessons = Lesson.query.filter_by(lesson_notes='', lesson_work='', completed=False).order_by(Lesson.lesson_date).all()

    # Sort students by the number of scheduled lessons in descending order
    students.sort(key=lambda s: len(s.scheduled_lesson_ids), reverse=True)

    return render_template('task manager.html', students=students, unplanned_lessons=unplanned_lessons)

if __name__ == '__main__':
    app.run(debug=True)