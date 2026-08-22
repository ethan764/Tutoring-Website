from flask import Flask, redirect, render_template, request, url_for, abort
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask_login import LoginManager, UserMixin, login_required, login_user, logout_user, current_user
from flask_wtf import FlaskForm
from wtforms import PasswordField, PasswordField, SubmitField, StringField
from wtforms.validators import DataRequired, Email, Length, ValidationError
from flask_bcrypt import Bcrypt
from functools import wraps


app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///test.db'
app.config['SECRET_KEY'] = 'secret_key'
db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


ADMIN_USER_EMAILS = {'ethannguyen764@gmail.com', 'ethan.nguyen.tutoring@gmail.com'}
def admin_whitelist_check(f):
    @wraps(f)
    def wrapper(*args, **kwargs):
        if not current_user.is_authenticated:
            abort(401)
        if current_user.email not in ADMIN_USER_EMAILS:
            abort(403)
        return f(*args, **kwargs)
    return wrapper

class User(db.Model, UserMixin):
    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(150), unique=True, nullable=False)
    password_hashed = db.Column(db.String(150), nullable=False)

class RegisterForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(message='Please enter a valid email address.'), Length(min=6, max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    submit = SubmitField('Register')

    def validate_email(self, email):
        user = User.query.filter_by(email=email.data).first()
        if user:
            raise ValidationError('Email is already registered. Please choose a different one.')

class LoginForm(FlaskForm):
    email = StringField('Email', validators=[DataRequired(), Email(message='Please enter a valid email address.'), Length(min=6, max=100)])
    password = PasswordField('Password', validators=[DataRequired(), Length(min=6, max=20)])
    submit = SubmitField('Login')

@app.route('/login', methods=['GET', 'POST'])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(email=form.email.data).first()
        if user and bcrypt.check_password_hash(user.password_hashed, form.password.data):
            login_user(user)
            return redirect(url_for('index'))
        else:
            return render_template('login.html', form=form, title='Login', error='Invalid email or password.')
    return render_template('login.html', form=form, title='Login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        # Create new user
        hashed_password = bcrypt.generate_password_hash(form.password.data).decode('utf-8')
        user = User(email=form.email.data, password_hashed=hashed_password)
        db.session.add(user)
        db.session.commit()
        print(f"Registered new user: {user.email}")
        return redirect(url_for('login'))
    return render_template('register.html', form=form, title='Register')

@app.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('login'))

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def __repr__(self):
        return f'<Lesson for Student ID {self.student_id}>'

@app.route('/')
@login_required
@admin_whitelist_check
def index():
    students = Student.query.all() #todo order by soonest lesson
    return render_template('students.html', students=students)

@app.route('/update_schedule/<int:student_id>', methods=['POST'])
@login_required
@admin_whitelist_check
def update_schedule(student_id):
    student = Student.query.get_or_404(student_id)
    student.schedule = request.form.get('schedule').split(', ')
    db.session.commit()
    return redirect(url_for('index'))

@app.route('/update_student/<int:student_id>', methods=['POST'])
@login_required
@admin_whitelist_check
def update_student(student_id):
    student = Student.query.get_or_404(student_id)
    student.name = request.form.get('name')
    student.meeting_link = request.form.get('meeting_link')
    student.schedule = request.form.get('schedule').split(', ')
    student.general_notes = request.form.get('general_notes')
    db.session.commit()
    return redirect(url_for('student_chart', student_id=student.id))

@app.route('/add_student', methods=['POST'])
@login_required
@admin_whitelist_check
def add_student():
    name = request.form.get('name')
    meeting_link = request.form.get('meeting_link')
    schedule = request.form.get('schedule').split(', ')

    new_student = Student(name=name, meeting_link=meeting_link, schedule=schedule)
    db.session.add(new_student)
    db.session.commit()

    return redirect(url_for('index'))

@app.route('/student_chart/<int:student_id>')
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


@app.route('/record_lesson/<int:student_id>', methods=['POST'])
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

    return redirect(url_for('student_chart', student_id=student.id))

@app.route('/lesson_planner/<int:student_id>', methods=['GET', 'POST'])
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

        return redirect(url_for('task_manager', student_id=student.id))

    return render_template('lesson planner.html', student=student, lesson=None, previous_lessons=Lesson.query.filter_by(student_id=student.id).order_by(Lesson.lesson_date.desc()).all())

@app.route('/lesson_planner/<int:student_id>/<int:lesson_id>', methods=['GET', 'POST'])
@login_required
@admin_whitelist_check
def lesson_planner_edit_lesson(student_id, lesson_id):
    student = Student.query.get_or_404(student_id)
    lesson = Lesson.query.get_or_404(lesson_id)

    if request.method == 'POST':
        # Handle form submission for editing the lesson
        lesson.lesson_date = request.form.get('lesson_date')
        lesson.lesson_notes = request.form.get('lesson_notes')
        lesson.lesson_work = request.form.get('lesson_homework')
        db.session.commit()

        return redirect(url_for('student_chart', student_id=student.id))

    return render_template('lesson planner.html', student=student, lesson=lesson, previous_lessons=Lesson.query.filter_by(student_id=student.id).order_by(Lesson.lesson_date.desc()).all())


@app.route('/task_manager')
@login_required
@admin_whitelist_check
def task_manager():
    students = Student.query.filter(Student.schedule != []).all()

    unplanned_lessons = Lesson.query.filter_by(lesson_notes='', lesson_work='', completed=False).order_by(Lesson.lesson_date).all()

    # Sort students by the number of scheduled lessons in descending order
    students.sort(key=lambda s: len(s.scheduled_lesson_ids), reverse=False)
    print(students)

    return render_template('task manager.html', students=students, unplanned_lessons=unplanned_lessons)



if __name__ == '__main__':
    app.run(debug=True)