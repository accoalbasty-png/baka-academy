
import os
from datetime import datetime
from functools import wraps

from flask import (
    Flask, render_template, request, redirect,
    url_for, session, flash, jsonify
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash


# ==================================================
# APPLICATION CONFIGURATION
# ==================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY", "change-this-secret"
)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL", "sqlite:///baka_academy.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024

app.config["UPLOAD_FOLDER"] = os.path.join(
    app.static_folder, "uploads", "student_photos"
)

ALLOWED_PHOTO_EXTENSIONS = {"jpg", "jpeg", "png"}

db = SQLAlchemy(app)
migrate = Migrate(app, db)


# ==================================================
# DATABASE MODELS
# ==================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(30), nullable=False, default="teacher")
    is_active = db.Column(
        db.Boolean, nullable=False, default=True, server_default="1"
    )


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(30), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    grade = db.Column(db.String(10), nullable=False)
    section = db.Column(db.String(10), nullable=False)

    sex = db.Column(db.String(1))
    age = db.Column(db.Integer)

    family_contact_name = db.Column(db.String(150))
    family_phone = db.Column(db.String(30))
    previous_school = db.Column(db.String(150))
    photo_filename = db.Column(db.String(255))
    stream = db.Column(db.String(50))
    academic_year_ec = db.Column(db.String(30))
    academic_year_gc = db.Column(db.String(30))

    is_active = db.Column(
        db.Boolean, nullable=False, default=True, server_default="1"
    )
    left_at = db.Column(db.DateTime)


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )
    grade = db.Column(db.String(10), nullable=False)
    section = db.Column(db.String(10), nullable=False)
    subject = db.Column(db.String(80), nullable=False)


class Mark(db.Model):
    """Legacy marks are preserved."""

    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(
        db.Integer, db.ForeignKey("student.id"), nullable=False
    )
    teacher_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )
    subject = db.Column(db.String(80), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    score = db.Column(db.Integer, nullable=False)

    student = db.relationship("Student")


class AssessmentMark(db.Model):
    """Five-component assessment marks for each semester."""

    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer, db.ForeignKey("student.id"), nullable=False
    )
    teacher_id = db.Column(
        db.Integer, db.ForeignKey("user.id"), nullable=False
    )

    subject = db.Column(db.String(100), nullable=False)
    semester = db.Column(db.String(20), nullable=False)
    academic_year_ec = db.Column(db.String(30), nullable=False)

    quiz1 = db.Column(db.Float)
    assignment = db.Column(db.Float)
    midterm = db.Column(db.Float)
    quiz2 = db.Column(db.Float)
    final = db.Column(db.Float)

    created_at = db.Column(
        db.DateTime, nullable=False, default=datetime.utcnow
    )
    updated_at = db.Column(
        db.DateTime,
        nullable=False,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    student = db.relationship("Student")
    teacher = db.relationship("User")

    @property
    def total(self):
        scores = [
            self.quiz1,
            self.assignment,
            self.midterm,
            self.quiz2,
            self.final
        ]
        return round(sum(score or 0 for score in scores), 2)


class Subject(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), unique=True, nullable=False)
    is_active = db.Column(
        db.Boolean, nullable=False, default=True, server_default="1"
    )


class AcademicYear(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    academic_year_ec = db.Column(
        db.String(30), unique=True, nullable=False
    )
    academic_year_gc = db.Column(db.String(30), nullable=False)
    is_current = db.Column(
        db.Boolean, nullable=False, default=False, server_default="0"
    )


# ==================================================
# ACCESS CONTROL
# ==================================================

def logged_in(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
            return redirect(url_for("login"))

        user = db.session.get(User, session["user_id"])

        if not user or not user.is_active:
            session.clear()
            flash("Your account is inactive or unavailable.")
            return redirect(url_for("login"))

        return fn(*args, **kwargs)

    return wrapper


def admin_only(fn):
    @wraps(fn)
    @logged_in
    def wrapper(*args, **kwargs):
        user = db.session.get(User, session["user_id"])

        if not user or user.role != "admin":
            flash("Administrator access required.")
            return redirect(url_for("dashboard"))

        return fn(*args, **kwargs)

    return wrapper


def student_staff_only(fn):
    @wraps(fn)
    @logged_in
    def wrapper(*args, **kwargs):
        user = db.session.get(User, session["user_id"])

        if not user or user.role not in ["admin", "student_management"]:
            flash("Student Management access required.")
            return redirect(url_for("dashboard"))

        return fn(*args, **kwargs)

    return wrapper


# ==================================================
# HELPER FUNCTIONS
# ==================================================

def allowed_photo(filename):
    return (
        "." in filename
        and filename.rsplit(".", 1)[1].lower()
        in ALLOWED_PHOTO_EXTENSIONS
    )


def generate_student_id():
    last_student = Student.query.order_by(Student.id.desc()).first()
    next_number = last_student.id + 1 if last_student else 1
    return f"BA-{next_number:05d}"


def get_student_form_data():
    age_text = request.form.get("age", "").strip()

    try:
        age = int(age_text) if age_text else None
    except ValueError:
        age = -1

    return {
        "full_name": request.form.get("full_name", "").strip(),
        "sex": request.form.get("sex", "").strip().upper(),
        "age": age,
        "family_contact_name": request.form.get(
            "family_contact_name", ""
        ).strip(),
        "family_phone": request.form.get("family_phone", "").strip(),
        "grade": request.form.get("grade", "").strip(),
        "section": request.form.get("section", "").strip(),
        "previous_school": request.form.get("previous_school", "").strip(),
        "stream": request.form.get("stream", "").strip(),
        "academic_year_ec": request.form.get(
            "academic_year_ec", ""
        ).strip(),
        "academic_year_gc": request.form.get(
            "academic_year_gc", ""
        ).strip(),
    }


def valid_student_form_data(data):
    if not all([
        data["full_name"],
        data["grade"],
        data["section"],
        data["academic_year_ec"]
    ]):
        return False

    if data["age"] == -1:
        return False

    if data["age"] is not None and not 1 <= data["age"] <= 100:
        return False

    if data["sex"] not in ["", "M", "F"]:
        return False

    return True


def save_student_photo(photo, filename):
    os.makedirs(app.config["UPLOAD_FOLDER"], exist_ok=True)
    photo.save(os.path.join(app.config["UPLOAD_FOLDER"], filename))


def get_school_subject_names():
    names = set()

    for subject in Subject.query.filter_by(is_active=True).all():
        names.add(subject.name.strip())

    for assignment in Assignment.query.all():
        if assignment.subject:
            names.add(assignment.subject.strip())

    for mark in AssessmentMark.query.all():
        if mark.subject:
            names.add(mark.subject.strip())

    return sorted(name for name in names if name)


def normalize_semester(value):
    if value in ["Term 1", "Semester 1"]:
        return "Semester 1"

    if value in ["Term 2", "Semester 2"]:
        return "Semester 2"

    return None


# ==================================================
# HOME AND LOGIN
# ==================================================

@app.route("/")
def home():
    if session.get("user_id"):
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")

        user = User.query.filter_by(username=username).first()

        if (
            user
            and user.is_active
            and check_password_hash(user.password_hash, password)
        ):
            session.clear()
            session["user_id"] = user.id
            session["role"] = user.role
            return redirect(url_for("dashboard"))

        flash("Incorrect username or password.")

    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# ==================================================
# DASHBOARD
# ==================================================

@app.route("/dashboard")
@logged_in
def dashboard():
    user = db.session.get(User, session["user_id"])
    return render_template("dashboard.html", user=user)


# ==================================================
# TEACHER ASSESSMENT ENTRY
# ==================================================

@app.route("/teacher/marks", methods=["GET", "POST"])
@logged_in
def marks():
    user = db.session.get(User, session["user_id"])

    if user.role not in ["admin", "teacher"]:
        flash("You are not allowed to enter marks.")
        return redirect(url_for("dashboard"))

    assignments = (
        Assignment.query.order_by(
            Assignment.grade,
            Assignment.section,
            Assignment.subject
        ).all()
        if user.role == "admin"
        else Assignment.query.filter_by(
            teacher_id=user.id
        ).order_by(
            Assignment.grade,
            Assignment.section,
            Assignment.subject
        ).all()
    )

    assignment_id = request.values.get("assignment_id", type=int)

    selected = next(
        (a for a in assignments if a.id == assignment_id),
        assignments[0] if assignments else None
    )

    term_value = request.values.get("term", "Semester 1")
    term = normalize_semester(term_value) or "Semester 1"

    students = (
        Student.query.filter_by(
            grade=selected.grade,
            section=selected.section,
            is_active=True
        ).order_by(Student.full_name).all()
        if selected else []
    )

    if request.method == "POST" and selected:
        for student in students:
            raw = request.form.get(
                f"score_{student.id}", ""
            ).strip()

            if not raw:
                continue

            try:
                score = int(raw)
            except ValueError:
                flash("Enter whole-number marks from 0 to 100.")
                return redirect(url_for(
                    "marks",
                    assignment_id=selected.id,
                    term=term
                ))

            if not 0 <= score <= 100:
                flash("Marks must be between 0 and 100.")
                return redirect(url_for(
                    "marks",
                    assignment_id=selected.id,
                    term=term
                ))

            mark = Mark.query.filter_by(
                student_id=student.id,
                teacher_id=user.id,
                subject=selected.subject,
                term=term
            ).first()

            if mark:
                mark.score = score
            else:
                db.session.add(Mark(
                    student_id=student.id,
                    teacher_id=user.id,
                    subject=selected.subject,
                    term=term,
                    score=score
                ))

        db.session.commit()
        flash("Legacy marks saved.")

        return redirect(url_for(
            "marks",
            assignment_id=selected.id,
            term=term
        ))

    assessment_existing = {}

    if selected and students:
        student_ids = [student.id for student in students]

        saved_marks = AssessmentMark.query.filter(
            AssessmentMark.student_id.in_(student_ids),
            AssessmentMark.subject == selected.subject,
            AssessmentMark.semester == term
        ).all()

        student_years = {
            student.id: (student.academic_year_ec or "").strip()
            for student in students
        }

        for saved in saved_marks:
            expected_year = student_years.get(saved.student_id, "")

            if (
                expected_year
                and saved.academic_year_ec == expected_year
            ):
                assessment_existing[saved.student_id] = saved

    existing = {}

    if selected:
        marks_query = Mark.query.filter_by(
            subject=selected.subject,
            term=term
        )

        if user.role != "admin":
            marks_query = marks_query.filter_by(
                teacher_id=user.id
            )

        for mark in marks_query.all():
            existing[mark.student_id] = mark.score

    return render_template(
        "marks.html",
        assignments=assignments,
        selected=selected,
        students=students,
        existing=existing,
        assessment_existing=assessment_existing,
        term=term
    )


# ==================================================
# AUTOMATIC ASSESSMENT SAVE
# ==================================================

@app.route(
    "/teacher/assessment/<int:student_id>/save",
    methods=["POST"]
)
@logged_in
def save_assessment(student_id):
    user = db.session.get(User, session["user_id"])

    if user.role not in ["admin", "teacher"]:
        return jsonify({
            "success": False,
            "message": "You are not allowed to enter marks."
        }), 403

    student = db.session.get(Student, student_id)

    if not student or not student.is_active:
        return jsonify({
            "success": False,
            "message": "Active student not found."
        }), 404

    academic_year = (student.academic_year_ec or "").strip()

    if not academic_year:
        return jsonify({
            "success": False,
            "message": (
                "This student's Ethiopian academic year is missing "
                "from their profile. Update the student information first."
            )
        }), 400

    data = request.get_json(silent=True) or {}

    subject = str(data.get("subject", "")).strip()
    semester = str(data.get("semester", "")).strip()
    component = str(data.get("component", "")).strip()

    allowed_components = {
        "quiz1": 10,
        "assignment": 10,
        "midterm": 30,
        "quiz2": 10,
        "final": 40
    }

    if (
        not subject
        or semester not in ["Semester 1", "Semester 2"]
        or component not in allowed_components
    ):
        return jsonify({
            "success": False,
            "message": "Invalid assessment information."
        }), 400

    if user.role == "teacher":
        assigned = Assignment.query.filter_by(
            teacher_id=user.id,
            grade=student.grade,
            section=student.section,
            subject=subject
        ).first()

        if not assigned:
            return jsonify({
                "success": False,
                "message": (
                    "You are not assigned to this subject and class."
                )
            }), 403

    elif user.role != "admin":
        return jsonify({
            "success": False,
            "message": "You are not allowed to enter marks."
        }), 403

    raw_score = data.get("score")

    if raw_score is None or raw_score == "":
        score = None
    else:
        try:
            score = float(raw_score)
        except (TypeError, ValueError):
            return jsonify({
                "success": False,
                "message": "Enter a valid number."
            }), 400

        if score < 0 or score > allowed_components[component]:
            return jsonify({
                "success": False,
                "message": (
                    f"{component} must be between 0 and "
                    f"{allowed_components[component]}."
                )
            }), 400

    assessment = AssessmentMark.query.filter_by(
        student_id=student.id,
        subject=subject,
        semester=semester,
        academic_year_ec=academic_year
    ).first()

    if not assessment:
        assessment = AssessmentMark(
            student_id=student.id,
            teacher_id=user.id,
            subject=subject,
            semester=semester,
            academic_year_ec=academic_year
        )
        db.session.add(assessment)

    setattr(assessment, component, score)
    assessment.teacher_id = user.id
    assessment.updated_at = datetime.utcnow()

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        return jsonify({
            "success": False,
            "message": "The mark could not be saved."
        }), 500

    return jsonify({
        "success": True,
        "message": "Mark saved automatically.",
        "total": assessment.total,
        "academic_year_ec": academic_year
    })


# ==================================================
# STUDENT MANAGEMENT DASHBOARD
# ==================================================

@app.route("/students")
@student_staff_only
def student_management():
    students = Student.query.filter_by(
        is_active=True
    ).order_by(
        Student.grade,
        Student.section,
        Student.full_name
    ).all()

    departed_count = Student.query.filter_by(
        is_active=False
    ).count()

    male_count = sum(
        1 for student in students if student.sex == "M"
    )

    female_count = sum(
        1 for student in students if student.sex == "F"
    )

    grades = ["9", "10", "11", "12"]

    male_by_grade = {}
    female_by_grade = {}

    for grade in grades:
        male_by_grade[grade] = sum(
            1 for student in students
            if student.grade == grade and student.sex == "M"
        )

        female_by_grade[grade] = sum(
            1 for student in students
            if student.grade == grade and student.sex == "F"
        )

    recent_students = Student.query.order_by(
        Student.id.desc()
    ).limit(8).all()

    return render_template(
        "students.html",
        students=students,
        total_students=len(students),
        male_count=male_count,
        female_count=female_count,
        departed_count=departed_count,
        male_by_grade=male_by_grade,
        female_by_grade=female_by_grade,
        grades=grades,
        recent_students=recent_students
    )


# ==================================================
# SEPARATE STUDENT LIST PAGE
# ==================================================

@app.route("/students/list")
@student_staff_only
def student_list():
    search = request.args.get("search", "").strip()

    query = Student.query.filter_by(is_active=True)

    if search:
        search_term = f"%{search}%"

        query = query.filter(
            db.or_(
                Student.full_name.ilike(search_term),
                Student.student_id.ilike(search_term),
                Student.family_phone.ilike(search_term)
            )
        )

    students = query.order_by(
        Student.grade,
        Student.section,
        Student.full_name
    ).all()

    return render_template(
        "student_list.html",
        students=students,
        search=search
    )


# ==================================================
# STUDENT REGISTRATION
# ==================================================

@app.route("/students/register", methods=["GET", "POST"])
@student_staff_only
def register_student():
    if request.method == "POST":
        data = get_student_form_data()

        if not valid_student_form_data(data):
            flash("Check the required fields, sex and age.")
            return render_template("register_student.html")

        photo = request.files.get("photo")
        photo_filename = None

        if photo and photo.filename:
            if not allowed_photo(photo.filename):
                flash("Student photo must be JPG, JPEG, or PNG.")
                return render_template("register_student.html")

            extension = photo.filename.rsplit(".", 1)[1].lower()

            photo_filename = (
                f"{generate_student_id().lower()}_"
                f"{int(datetime.utcnow().timestamp())}.{extension}"
            )

            save_student_photo(photo, photo_filename)

        student = Student(
            student_id=generate_student_id(),
            full_name=data["full_name"],
            sex=data["sex"] or None,
            age=data["age"],
            family_contact_name=data["family_contact_name"],
            family_phone=data["family_phone"],
            grade=data["grade"],
            section=data["section"],
            previous_school=data["previous_school"],
            stream=data["stream"],
            academic_year_ec=data["academic_year_ec"],
            academic_year_gc=data["academic_year_gc"],
            photo_filename=photo_filename,
            is_active=True
        )

        db.session.add(student)
        db.session.commit()

        flash(
            f"Student registered successfully. "
            f"Student ID: {student.student_id}"
        )

        return redirect(url_for(
            "student_profile",
            student_id=student.id
        ))

    return render_template("register_student.html")


# ==================================================
# STUDENT ID CARD
# ==================================================

@app.route("/students/<int:student_id>/id-card")
@student_staff_only
def student_id_card(student_id):
    student = db.session.get(Student, student_id)

    if not student:
        flash("Student not found.")
        return redirect(url_for("student_management"))

    return render_template(
        "student_id_card.html",
        student=student
    )


# ==================================================
# STUDENT PROFILE AND REPORT CARD
# ==================================================

@app.route("/students/<int:student_id>")
@student_staff_only
def student_profile(student_id):
    student = db.session.get(Student, student_id)

    if not student:
        flash("Student not found.")
        return redirect(url_for("student_management"))

    marks = Mark.query.filter_by(
        student_id=student.id
    ).order_by(
        Mark.subject,
        Mark.term
    ).all()

    assessment_marks = AssessmentMark.query.filter_by(
        student_id=student.id,
        academic_year_ec=(student.academic_year_ec or "")
    ).order_by(
        AssessmentMark.subject,
        AssessmentMark.semester
    ).all()

    subjects = get_school_subject_names()

    for mark in marks:
        if mark.subject and mark.subject not in subjects:
            subjects.append(mark.subject)

    for mark in assessment_marks:
        if mark.subject and mark.subject not in subjects:
            subjects.append(mark.subject)

    subjects = sorted(set(subjects))

    return render_template(
        "student_profile.html",
        student=student,
        marks=marks,
        assessment_marks=assessment_marks,
        subjects=subjects
    )


# ==================================================
# EDIT STUDENT INFORMATION
# ==================================================

@app.route("/students/<int:student_id>/edit", methods=["GET", "POST"])
@student_staff_only
def edit_student(student_id):
    student = db.session.get(Student, student_id)

    if not student:
        flash("Student not found.")
        return redirect(url_for("student_management"))

    if request.method == "POST":
        data = get_student_form_data()

        if not valid_student_form_data(data):
            flash("Check the required fields, sex and age.")
            return render_template(
                "edit_student.html",
                student=student
            )

        student.full_name = data["full_name"]
        student.sex = data["sex"] or None
        student.age = data["age"]
        student.family_contact_name = data["family_contact_name"]
        student.family_phone = data["family_phone"]
        student.grade = data["grade"]
        student.section = data["section"]
        student.previous_school = data["previous_school"]
        student.stream = data["stream"]
        student.academic_year_ec = data["academic_year_ec"]
        student.academic_year_gc = data["academic_year_gc"]

        photo = request.files.get("photo")

        if photo and photo.filename:
            if not allowed_photo(photo.filename):
                flash("Student photo must be JPG, JPEG, or PNG.")
                return render_template(
                    "edit_student.html",
                    student=student
                )

            extension = photo.filename.rsplit(".", 1)[1].lower()

            new_filename = (
                f"{student.student_id.lower()}_"
                f"{int(datetime.utcnow().timestamp())}.{extension}"
            )

            save_student_photo(photo, new_filename)
            student.photo_filename = new_filename

        db.session.commit()
        flash("Student information updated.")

        return redirect(url_for(
            "student_profile",
            student_id=student.id
        ))

    return render_template(
        "edit_student.html",
        student=student
    )


# ==================================================
# DEACTIVATE STUDENT - NEVER DELETE RECORDS
# ==================================================

@app.route(
    "/students/<int:student_id>/deactivate",
    methods=["POST"]
)
@student_staff_only
def deactivate_student(student_id):
    student = db.session.get(Student, student_id)

    if not student:
        flash("Student not found.")
        return redirect(url_for("student_list"))

    if student.is_active:
        student.is_active = False
        student.left_at = datetime.utcnow()
        db.session.commit()
        flash("Student moved to the Left Student List.")

    return redirect(url_for("student_list"))


# ==================================================
# LEFT STUDENT LIST
# ==================================================

@app.route("/students/left")
@student_staff_only
def left_students():
    students = Student.query.filter_by(
        is_active=False
    ).order_by(
        Student.left_at.desc()
    ).all()

    return render_template(
        "left_students.html",
        students=students
    )


# ==================================================
# STUDENT RESULT LIST
# ==================================================

@app.route("/students/results")
@student_staff_only
def student_results():
    search = request.args.get("search", "").strip()

    query = Student.query

    if search:
        search_term = f"%{search}%"

        query = query.filter(
            db.or_(
                Student.full_name.ilike(search_term),
                Student.student_id.ilike(search_term)
            )
        )

    students = query.order_by(
        Student.grade,
        Student.section,
        Student.full_name
    ).all()

    return render_template(
        "student_results.html",
        students=students,
        search=search
    )


# ==================================================
# ADMINISTRATION
# ==================================================

@app.route("/admin")
@admin_only
def admin():
    return render_template(
        "admin.html",
        teachers=User.query.filter_by(
            role="teacher",
            is_active=True
        ).all(),
        students=Student.query.filter_by(
            is_active=True
        ).order_by(
            Student.grade,
            Student.section,
            Student.full_name
        ).all(),
        assignments=Assignment.query.all(),
        student_staff=User.query.filter_by(
            role="student_management",
            is_active=True
        ).all()
    )


# ==================================================
# CREATE TEACHER ACCOUNT
# ==================================================

@app.route("/admin/create-teacher", methods=["POST"])
@admin_only
def create_teacher():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username:
        flash("Enter a teacher username.")
    elif len(password) < 8:
        flash("Password must be at least 8 characters.")
    elif User.query.filter_by(username=username).first():
        flash("Username already exists.")
    else:
        db.session.add(User(
            username=username,
            password_hash=generate_password_hash(password),
            role="teacher",
            is_active=True
        ))
        db.session.commit()
        flash("Teacher account created.")

    return redirect(url_for("admin"))


# ==================================================
# CREATE STUDENT MANAGEMENT STAFF ACCOUNT
# ==================================================

@app.route("/admin/create-student-staff", methods=["POST"])
@admin_only
def create_student_staff():
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not username:
        flash("Enter a staff username.")
    elif len(password) < 8:
        flash("Password must be at least 8 characters.")
    elif User.query.filter_by(username=username).first():
        flash("Username already exists.")
    else:
        db.session.add(User(
            username=username,
            password_hash=generate_password_hash(password),
            role="student_management",
            is_active=True
        ))
        db.session.commit()
        flash("Student Management staff account created.")

    return redirect(url_for("admin"))


# ==================================================
# ASSIGN TEACHER TO CLASS AND SUBJECT
# ==================================================

@app.route("/admin/assign", methods=["POST"])
@admin_only
def assign_teacher():
    teacher = db.session.get(
        User,
        request.form.get("teacher_id", type=int)
    )

    if (
        not teacher
        or teacher.role != "teacher"
        or not teacher.is_active
    ):
        flash("Select an active teacher.")
        return redirect(url_for("admin"))

    subject_name = request.form.get("subject", "").strip()
    grade = request.form.get("grade", "").strip()
    section = request.form.get("section", "").strip()

    if not subject_name or not grade or not section:
        flash("Complete all assignment fields.")
        return redirect(url_for("admin"))

    db.session.add(Assignment(
        teacher_id=teacher.id,
        grade=grade,
        section=section,
        subject=subject_name
    ))

    subject = Subject.query.filter_by(
        name=subject_name
    ).first()

    if not subject:
        db.session.add(Subject(name=subject_name))

    db.session.commit()
    flash("Assignment saved.")

    return redirect(url_for("admin"))


# ==================================================
# LEGACY ADMIN ADD STUDENT ROUTE
# ==================================================

@app.route("/admin/add-student", methods=["POST"])
@admin_only
def add_student():
    name = request.form.get("full_name", "").strip()
    grade = request.form.get("grade", "").strip()
    section = request.form.get("section", "").strip()

    if not name or not grade or not section:
        flash("Complete all student fields.")
        return redirect(url_for("admin"))

    sid = generate_student_id()

    db.session.add(Student(
        student_id=sid,
        full_name=name,
        grade=grade,
        section=section,
        is_active=True
    ))

    db.session.commit()
    flash(f"Student added: {sid}")

    return redirect(url_for("admin"))


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":
    app.run(debug=True)
