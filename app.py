import os
from functools import wraps
from flask import Flask, render_template, request, redirect, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-this-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL", "sqlite:///baka_academy.db")
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db = SQLAlchemy(app)

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), nullable=False, default="teacher")

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(30), unique=True, nullable=False)
    full_name = db.Column(db.String(150), nullable=False)
    grade = db.Column(db.String(10), nullable=False)
    section = db.Column(db.String(10), nullable=False)

class Assignment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    grade = db.Column(db.String(10), nullable=False)
    section = db.Column(db.String(10), nullable=False)
    subject = db.Column(db.String(80), nullable=False)

class Mark(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"), nullable=False)
    teacher_id = db.Column(db.Integer, db.ForeignKey("user.id"), nullable=False)
    subject = db.Column(db.String(80), nullable=False)
    term = db.Column(db.String(20), nullable=False)
    score = db.Column(db.Integer, nullable=False)
    student = db.relationship("Student")

def logged_in(fn):
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if "user_id" not in session:
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

@app.route("/")
def home():
    return redirect(url_for("dashboard") if session.get("user_id") else url_for("login"))

@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        user = User.query.filter_by(username=request.form["username"].strip()).first()
        if user and check_password_hash(user.password_hash, request.form["password"]):
            session.clear()
            session["user_id"] = user.id
            return redirect(url_for("dashboard"))
        flash("Incorrect username or password.")
    return render_template("login.html")

@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/dashboard")
@logged_in
def dashboard():
    user = db.session.get(User, session["user_id"])
    return render_template("dashboard.html", user=user)

@app.route("/teacher/marks", methods=["GET", "POST"])
@logged_in
def marks():
    user = db.session.get(User, session["user_id"])
    assignments = Assignment.query.all() if user.role == "admin" else Assignment.query.filter_by(teacher_id=user.id).all()
    assignment_id = request.values.get("assignment_id", type=int)
    selected = next((a for a in assignments if a.id == assignment_id), assignments[0] if assignments else None)
    term = request.values.get("term", "Term 1")
    students = Student.query.filter_by(grade=selected.grade, section=selected.section).order_by(Student.full_name).all() if selected else []

    if request.method == "POST" and selected:
        for student in students:
            raw = request.form.get(f"score_{student.id}", "").strip()
            if not raw:
                continue
            try:
                score = int(raw)
            except ValueError:
                flash("Enter whole-number marks from 0 to 100.")
                return redirect(url_for("marks", assignment_id=selected.id, term=term))
            if not 0 <= score <= 100:
                flash("Marks must be between 0 and 100.")
                return redirect(url_for("marks", assignment_id=selected.id, term=term))
            mark = Mark.query.filter_by(student_id=student.id, teacher_id=user.id, subject=selected.subject, term=term).first()
            if mark:
                mark.score = score
            else:
                db.session.add(Mark(student_id=student.id, teacher_id=user.id, subject=selected.subject, term=term, score=score))
        db.session.commit()
        flash("Marks saved.")
        return redirect(url_for("marks", assignment_id=selected.id, term=term))

    existing = {}
    if selected:
        for mark in Mark.query.filter_by(teacher_id=user.id, subject=selected.subject, term=term).all():
            existing[mark.student_id] = mark.score
    return render_template("marks.html", assignments=assignments, selected=selected, students=students, existing=existing, term=term)

@app.route("/admin")
@admin_only
def admin():
    return render_template("admin.html",
        teachers=User.query.filter_by(role="teacher").all(),
        students=Student.query.order_by(Student.grade, Student.section, Student.full_name).all(),
        assignments=Assignment.query.all())

@app.route("/admin/create-teacher", methods=["POST"])
@admin_only
def create_teacher():
    username, password = request.form["username"].strip(), request.form["password"]
    if len(password) < 8:
        flash("Password must be at least 8 characters.")
    elif User.query.filter_by(username=username).first():
        flash("Username already exists.")
    else:
        db.session.add(User(username=username, password_hash=generate_password_hash(password), role="teacher"))
        db.session.commit()
        flash("Teacher account created.")
    return redirect(url_for("admin"))

@app.route("/admin/assign", methods=["POST"])
@admin_only
def assign_teacher():
    teacher = db.session.get(User, request.form.get("teacher_id", type=int))
    if not teacher or teacher.role != "teacher":
        flash("Select a valid teacher.")
    else:
        db.session.add(Assignment(teacher_id=teacher.id, grade=request.form["grade"],
            section=request.form["section"].strip(), subject=request.form["subject"].strip()))
        db.session.commit()
        flash("Assignment saved.")
    return redirect(url_for("admin"))

@app.route("/admin/add-student", methods=["POST"])
@admin_only
def add_student():
    name = request.form["full_name"].strip()
    if name:
        sid = f"BA-{Student.query.count()+1:05d}"
        db.session.add(Student(student_id=sid, full_name=name, grade=request.form["grade"], section=request.form["section"].strip()))
        db.session.commit()
        flash(f"Student added: {sid}")
    return redirect(url_for("admin"))

with app.app_context():
    db.create_all()
    if not User.query.filter_by(username="admin").first():
        db.session.add(User(username="admin", password_hash=generate_password_hash(os.environ.get("ADMIN_PASSWORD", "ChangeMe123!")), role="admin"))
        db.session.commit()

if __name__ == "__main__":
    app.run(debug=True)
