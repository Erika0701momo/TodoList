from flask import Flask, abort, render_template, redirect, url_for, flash, request
from flask_bootstrap import Bootstrap5
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Date, Boolean, or_
from werkzeug.security import generate_password_hash, check_password_hash
from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, PasswordField, DateField, BooleanField, SelectField
from wtforms.validators import DataRequired, Email
import datetime


app = Flask(__name__)
app.config["SECRET_KEY"] = "73f5e7ae413742c3856abd2e16580293"
Bootstrap5(app)

class Base(DeclarativeBase):
    pass

app.config["SQLALCHEMY_DATABASE_URI"] = "sqlite:///todo.db"
db = SQLAlchemy(model_class=Base)
db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)

@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)

#テーブル作成
class User(UserMixin, db.Model):
    __tablename__ = "users"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    email: Mapped[str] = mapped_column(String, unique=True, nullable=False)
    password: Mapped[str] = mapped_column(String, nullable=False)
    name: Mapped[str] = mapped_column(String, nullable=False)

    tasks = relationship("Task", back_populates="user")

class Task(db.Model):
    __tablename__ = "tasks"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, db.ForeignKey("users.id"))
    task_name: Mapped[str] = mapped_column(String, nullable=False)
    registration_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    due_date: Mapped[datetime.date] = mapped_column(Date, nullable=False)
    is_done: Mapped[bool] = mapped_column(Boolean, nullable=False)

    user = relationship("User", back_populates="tasks")

with app.app_context():
    db.create_all()

#フォーム
class LoginForm(FlaskForm):
    email = StringField("メールアドレス", validators=[DataRequired(message="メールアドレスは必須入力です。"), Email(message="正しいメールアドレスを入力してください。")])
    password = PasswordField("パスワード", validators=[DataRequired(message="パスワードは必須入力です。")])
    submit_login = SubmitField("ログイン")
    submit_register = SubmitField("新規登録")

class RegisterForm(FlaskForm):
    email = StringField("メールアドレス", validators=[DataRequired(message="メールアドレスは必須入力です。"), Email(message="正しいメールアドレスを入力してください。")])
    password = PasswordField("パスワード", validators=[DataRequired(message="パスワードは必須入力です。")])
    name = StringField("名前", validators=[DataRequired(message="名前は必須入力です。")])
    submit = SubmitField("登録")

class CreateTaskForm(FlaskForm):
    task_name = StringField("タスク名", validators=[DataRequired(message="タスク名は必須入力です。")])
    charge = SelectField("担当者", validators=[DataRequired(message="担当者は必須入力です。")])
    due_date = DateField("日付を記入してください:", format="%Y-%m-%d", validators=[DataRequired(message="日付は必須入力です。")])
    is_done = BooleanField("完了")
    submit = SubmitField("登録")
    cancel = SubmitField("キャンセル")

class SearchForm(FlaskForm):
    search = StringField()
    submit = SubmitField("検索")

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.submit_register.data:
        return redirect(url_for('register'))
    if form.validate_on_submit():
        email = form.email.data
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == email))
        user = result.scalar()
        if user and check_password_hash(user.password, password):
            login_user(user)
            return redirect(url_for("get_tasks"))
        elif not user:
            flash("メールアドレスが違います。")
            return redirect(url_for("login"))
        elif not check_password_hash(user.password, password):
            flash("パスワードが違います。")
            return redirect(url_for("login"))
    return render_template("login.html", form=form, current_user=current_user)

@app.route("/register", methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            flash("既にそのメールアドレスで登録されています。ログインしてください。")
            return redirect(url_for("login"))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method="pbkdf2:sha256",
            salt_length=8
        )
        new_user = User(
            email = form.email.data,
            password = hash_and_salted_password,
            name = form.name.data
        )
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for("get_tasks"))
    return render_template("register.html", form=form, current_user=current_user)

@app.route("/", methods=["GET", "POST"])
def get_tasks():
    form = SearchForm()
    if request.method == "POST":
        search_word = form.search.data
        result = db.session.execute(db.select(Task).where(or_(User.name.contains(search_word)).order_by(Task.due_date)))
        if result:
            print("result")
            tasks = result.scalars().all()
            title = "検索結果"
            today = datetime.date.today()
            return render_template("index.html", current_user=current_user,tasks=tasks, title=title, today=today, form=form)
        else:
            print("no result")
    else:
        result = db.session.execute(db.select(Task).where(Task.is_done == 0).order_by(Task.due_date))
        tasks = result.scalars()
        today = datetime.date.today()
        return render_template("index.html", current_user=current_user, form=form, tasks=tasks, today=today)

@app.route("/create", methods=["GET", "POST"])
def create_task():
    form = CreateTaskForm()
    form.charge.choices = [(r.id, r.name) for r in User.query.all()]
    title = "タスク登録"
    if form.cancel.data:
        return redirect(url_for("get_tasks"))
    if form.validate_on_submit():
        new_task = Task(
            user_id=form.charge.data,
            task_name=form.task_name.data,
            registration_date=datetime.date.today(),
            due_date=form.due_date.data,
            is_done=form.is_done.data
        )
        db.session.add(new_task)
        db.session.commit()
        return redirect(url_for("get_tasks"))
    return render_template("task.html", form=form, title=title, current_user=current_user)

@app.route("/logout")
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)

    # (Task.task_name.contains(search_word)),