import os
from functools import wraps

from flask import (
    Flask,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash
)
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from werkzeug.security import generate_password_hash, check_password_hash


# ==================================================
# APPLICATION CONFIGURATION
# ==================================================

app = Flask(__name__)

app.config["SECRET_KEY"] = os.environ.get(
    "SECRET_KEY",
    "change-this-secret"
)

app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "sqlite:///baka_academy.db"
)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(app)
migrate = Migrate(app, db)


# ==================================================
# DATABASE MODELS
# ==================================================

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(
        db.String(80),
        unique=True,
        nullable=False
    )

    password_hash = db.Column(
        db.String(255),
        nullable=False
    )

    role = db.Column(
        db.String(30),
        nullable=False,
        default="teacher"
    )

    # Inactive users cannot log in.
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default="1"
    )


class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )

    full_name = db.Column(
        db.String(150),
        nullable=False
    )

    grade = db.Column(
        db.String(10),
        nullable=False
    )

    section = db.Column(
        db.String(10),
        nullable=False
    )

    # Additional student profile information.
    family_contact_name = db.Column(db.String(150))
    family_phone = db.Column(db.String(30))
    previous_school = db.Column(db.String(150))
    photo_filename = db.Column(db.String(255))

    # Academic stream, for example Natural Science
    # or Social Science.
    stream = db.Column(db.String(50))

    # E.C. is the primary academic-year calendar.
    # G.C. is stored alongside it.
    academic_year_ec = db.Column(db.String(30))
    academic_year_gc = db.Column(db.String(30))

    # Left students remain in the database.
    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default="1"
    )

    left_at = db.Column(db.DateTime)


class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    grade = db.Column(
        db.String(10),
        nullable=False
    )

    section = db.Column(
        db.String(10),
        nullable=False
    )

    subject = db.Column(
        db.String(80),
        nullable=False
    )


class Mark(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    student_id = db.Column(
        db.Integer,
        db.ForeignKey("student.id"),
        nullable=False
    )

    teacher_id = db.Column(
        db.Integer,
        db.ForeignKey("user.id"),
        nullable=False
    )

    subject = db.Column(
        db.String(80),
        nullable=False
    )

    term = db.Column(
        db.String(20),
        nullable=False
    )

    score = db.Column(
        db.Integer,
        nullable=False
    )

    student = db.relationship("Student")


class Subject(db.Model):
    """Subjects configured by the school administrator."""

    id = db.Column(db.Integer, primary_key=True)

    name = db.Column(
        db.String(100),
        unique=True,
        nullable=False
    )

    is_active = db.Column(
        db.Boolean,
        nullable=False,
        default=True,
        server_default="1"
    )


class AcademicYear(db.Model):
    """Academic years stored in both calendars."""

    id = db.Column(db.Integer, primary_key=True)

    # Example: 2018 E.C.
    academic_year_ec = db.Column(
        db.String(30),
        unique=True,
        nullable=False
    )

    # Example: 2025/2026 G.C.
    academic_year_gc = db.Column(
        db.String(30),
        nullable=False
    )

    is_current = db.Column(
        db.Boolean,
        nullable=False,
        default=False,
        server_default="0"
    )


# ==================================================
# LOGIN AND ACCESS CONTROL
# ==================================================

def logged_in(fn):

    @wraps(fn)
    def wrapper(*args, **kwargs):

        if "user_id" not in session:
            return redirect(url_for("login"))

        user = db.session.get(
            User,
            session["user_id"]
        )

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

        user = db.session.get(
            User,
            session["user_id"]
        )

        if not user or user.role != "admin":
            flash("Administrator access required.")
            return redirect(url_for("dashboard"))

        return fn(*args, **kwargs)

    return wrapper


# ==================================================
# HOME PAGE
# ==================================================

@app.route("/")
def home():

    if session.get("user_id"):
        return redirect(url_for("dashboard"))

    return redirect(url_for("login"))


# ==================================================
# LOGIN
# ==================================================

@app.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form.get(
            "username",
            ""
        ).strip()

        password = request.form.get(
            "password",
            ""
        )

        user = User.query.filter_by(
            username=username
        ).first()

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


# ==================================================
# LOGOUT
# ==================================================

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

    user = db.session.get(
        User,
        session["user_id"]
    )

    return render_template(
        "dashboard.html",
        user=user
    )


# ==================================================
# TEACHER MARK ENTRY
# ==================================================

@app.route("/teacher/marks", methods=["GET", "POST"])
@logged_in
def marks():

    user = db.session.get(
        User,
        session["user_id"]
    )

    if user.role not in ["admin", "teacher"]:
        flash("You are not allowed to enter marks.")
        return redirect(url_for("dashboard"))

    assignments = (
        Assignment.query.all()
        if user.role == "admin"
        else Assignment.query.filter_by(
            teacher_id=user.id
        ).all()
    )

    assignment_id = request.values.get(
        "assignment_id",
        type=int
    )

    selected = next(
        (
            assignment
            for assignment in assignments
            if assignment.id == assignment_id
        ),
        assignments[0] if assignments else None
    )

    term = request.values.get(
        "term",
        "Term 1"
    )

    students = (
        Student.query.filter_by(
            grade=selected.grade,
            section=selected.section,
            is_active=True
        ).order_by(
            Student.full_name
        ).all()
        if selected else []
    )

    if request.method == "POST" and selected:

        for student in students:

            raw = request.form.get(
                f"score_{student.id}",
                ""
            ).strip()

            if not raw:
                continue

            try:
                score = int(raw)

            except ValueError:

                flash(
                    "Enter whole-number marks from 0 to 100."
                )

                return redirect(url_for(
                    "marks",
                    assignment_id=selected.id,
                    term=term
                ))

            if not 0 <= score <= 100:

                flash(
                    "Marks must be between 0 and 100."
                )

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
                db.session.add(
                    Mark(
                        student_id=student.id,
                        teacher_id=user.id,
                        subject=selected.subject,
                        term=term,
                        score=score
                    )
                )

        db.session.commit()

        flash("Marks saved.")

        return redirect(url_for(
            "marks",
            assignment_id=selected.id,
            term=term
        ))

    existing = {}

    if selected:

        for mark in Mark.query.filter_by(
            teacher_id=user.id,
            subject=selected.subject,
            term=term
        ).all():

            existing[mark.student_id] = mark.score

    return render_template(
        "marks.html",
        assignments=assignments,
        selected=selected,
        students=students,
        existing=existing,
        term=term
    )


# ==================================================
# STUDENT MANAGEMENT PAGE
# ==================================================

@app.route("/students")
@admin_only
def student_management():

    students = Student.query.filter_by(
        is_active=True
    ).order_by(
        Student.grade,
        Student.section,
        Student.full_name
    ).all()

    return render_template(
        "students.html",
        students=students
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

        assignments=Assignment.query.all()
    )


# ==================================================
# CREATE TEACHER ACCOUNT
# ==================================================

@app.route("/admin/create-teacher", methods=["POST"])
@admin_only
def create_teacher():

    username = request.form.get(
        "username",
        ""
    ).strip()

    password = request.form.get(
        "password",
        ""
    )

    if not username:
        flash("Enter a teacher username.")

    elif len(password) < 8:
        flash("Password must be at least 8 characters.")

    elif User.query.filter_by(username=username).first():
        flash("Username already exists.")

    else:

        db.session.add(
            User(
                username=username,
                password_hash=generate_password_hash(password),
                role="teacher",
                is_active=True
            )
        )

        db.session.commit()
        flash("Teacher account created.")

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

    if not teacher or teacher.role != "teacher" or not teacher.is_active:

        flash("Select an active teacher.")

    else:

        subject_name = request.form.get(
            "subject",
            ""
        ).strip()

        grade = request.form.get(
            "grade",
            ""
        ).strip()

        section = request.form.get(
            "section",
            ""
        ).strip()

        if not subject_name or not grade or not section:
            flash("Complete all assignment fields.")

        else:

            db.session.add(
                Assignment(
                    teacher_id=teacher.id,
                    grade=grade,
                    section=section,
                    subject=subject_name
                )
            )

            # Also register the subject if it is new.
            subject = Subject.query.filter_by(
                name=subject_name
            ).first()

            if not subject:
                db.session.add(
                    Subject(name=subject_name)
                )

            db.session.commit()
            flash("Assignment saved.")

    return redirect(url_for("admin"))


# ==================================================
# ADD STUDENT
# ==================================================

@app.route("/admin/add-student", methods=["POST"])
@admin_only
def add_student():

    name = request.form.get(
        "full_name",
        ""
    ).strip()

    if not name:
        flash("Enter the student's full name.")
        return redirect(url_for("admin"))

    last_student = Student.query.order_by(
        Student.id.desc()
    ).first()

    next_number = (
        last_student.id + 1
        if last_student
        else 1
    )

    sid = f"BA-{next_number:05d}"

    db.session.add(
        Student(
            student_id=sid,
            full_name=name,
            grade=request.form["grade"],
            section=request.form["section"].strip(),
            is_active=True
        )
    )

    db.session.commit()

    flash(f"Student added: {sid}")

    return redirect(url_for("admin"))


# ==================================================
# RUN APPLICATION
# ==================================================

if __name__ == "__main__":
    app.run(debug=True)