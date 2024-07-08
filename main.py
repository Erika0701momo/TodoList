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
from functools import wraps
from markupsafe import escape, Markup
from werkzeug.exceptions import HTTPException, default_exceptions


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

#デコレータ　ログインしていなかったらログイン画面へ遷移
def goto_login(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated:
            form = LoginForm()
            return render_template("login.html", form=form)
        return f(*args, **kwargs)
    return decorated_function

#エラーハンドリング
@app.errorhandler(HTTPException)
def custom_error(e):
    code = e.code
    name = escape(e.name)

    if e.description is None:
        description = ""
    else:
        description = e.description

    description = escape(description).replace("\n", Markup("<br>"))

    return render_template("error.html", code=code, name=name, description=description), code

# エラーコードをurlに打ち込むとそのエラーページを表示
@app.get("/<int:code>")
def error_page(code):
    if code not in [k for k in default_exceptions.keys()]:
        code = 500
    abort(code)

@app.route("/login", methods=["GET", "POST"])
def login():
    form = LoginForm()

    #　新規登録ボタンが押されたら新規登録画面へ遷移
    if form.submit_register.data:
        return redirect(url_for('register'))

    # ログイン処理
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
    title = "ユーザー登録"

    # 新規登録処理
    if form.validate_on_submit():
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()

        if user:
            flash("既にそのメールアドレスで登録されています。ログインしてください。")
            return redirect(url_for("login"))

        # パスワード暗号化
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

        # ユーザー登録
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)

        # タスク一覧画面へ
        return redirect(url_for("get_tasks"))

    return render_template("register.html", form=form, current_user=current_user, title=title)

@app.route("/", methods=["GET", "POST"])
@goto_login
def get_tasks():
    form = SearchForm()
    today = datetime.date.today()

    # POSTなら検索処理
    if request.method == "POST":
        search_word = form.search.data
        result = db.session.execute(db.select(Task).join(Task.user).where(or_(User.name.contains(search_word), (Task.task_name.contains(search_word)))).order_by(Task.due_date))
        tasks = result.scalars().all()

        if tasks:
            title = "検索結果"
            today = datetime.date.today()
            return render_template("index.html", current_user=current_user,tasks=tasks, title=title, today=today, form=form)
        else:
            flash("検索結果がありません。", "category1")
            return redirect(url_for("get_tasks"))

    # リクエストパラメータあったら完了済みタスク一覧を表示
    else:
        id = request.args.get("id")
        if id == "done":
            title = "完了済みタスク一覧"
            is_done = True
            result = db.session.execute(db.select(Task).where(Task.is_done == 1).order_by(Task.due_date))
            tasks = result.scalars().all()
            return render_template("index.html", current_user=current_user, tasks=tasks, title=title, form=form, today=today, is_done=is_done)
        # タスク一覧表示
        else:
            result = db.session.execute(db.select(Task).where(Task.is_done == 0).order_by(Task.due_date))
            tasks = result.scalars().all()
            title = "タスク一覧"
            return render_template("index.html", current_user=current_user, form=form, tasks=tasks, today=today, title=title)

@app.route("/create", methods=["GET", "POST"])
@goto_login
def create_task():
    form = CreateTaskForm()
    form.charge.choices = [(r.id, r.name) for r in User.query.all()]
    title = "タスク登録"

    # キャンセルボタン押したらタスク一覧画面へ
    if form.cancel.data:
        return redirect(url_for("get_tasks"))

    # タスク登録
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
        flash(f"タスク「{new_task.task_name}」を登録しました。", "category2")

        return redirect(url_for("get_tasks"))

    return render_template("task.html", form=form, title=title, current_user=current_user)

@app.route("/edit/<int:task_id>", methods=["GET", "POST"])
@goto_login
def edit_task(task_id):
    title = "タスク更新"
    task = db.get_or_404(Task, task_id)
    form = CreateTaskForm()

    # タスク更新画面表示
    if request.method == "GET":
        form.charge.choices = [(r.id, r.name) for r in User.query.all()]
        form.charge.default = task.user_id
        form.task_name.default = task.task_name
        form.due_date.default = task.due_date
        form.is_done.default = task.is_done
        form.process()

        return render_template("task.html", current_user=current_user, form=form, title=title, task=task)
    else:
        form.charge.choices = [(r.id, r.name) for r in User.query.all()]

        # キャンセルボタン押したらタスク一覧画面へ
        if form.cancel.data:
            return redirect(url_for("get_tasks"))

        # タスク更新
        if form.validate_on_submit():
            task.user_id = form.charge.data
            task.task_name = form.task_name.data
            task.due_date = form.due_date.data
            task.is_done = form.is_done.data

            db.session.commit()

            flash(f"タスク「{task.task_name}」を更新しました。", "category2")

            return redirect(url_for("get_tasks"))

@app.route("/delete/<int:task_id>", methods=["GET", "POST"])
@goto_login
def delete_task(task_id):
    task_to_delete = db.get_or_404(Task, task_id)

    # タスク削除画面表示
    if request.method == "GET":
       return render_template("delete.html", task=task_to_delete, current_user=current_user)
    else:
        # タスク削除
        if "delete" in request.form:
            db.session.delete(task_to_delete)
            db.session.commit()
            flash(f"タスク「{task_to_delete.task_name}」を削除しました。", "category2")
            return redirect(url_for("get_tasks"))
        # キャンセルボタン押したらタスク一覧画面へ
        elif "cancel" in request.form:
            return redirect(url_for("get_tasks"))

@app.route("/complete/<int:task_id>")
@goto_login
def complete_task(task_id):
    # タスクを完了にする
    task = db.get_or_404(Task, task_id)
    task.is_done = True
    db.session.commit()
    flash(f"タスク「{task.task_name}」を完了しました。", "category2")
    return redirect(url_for("get_tasks"))

@app.route("/logout")
@goto_login
def logout():
    logout_user()
    return redirect(url_for('login'))

if __name__ == "__main__":
    app.run(debug=True)

