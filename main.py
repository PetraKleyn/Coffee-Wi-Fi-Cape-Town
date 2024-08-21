from flask import Flask, abort, render_template, redirect, url_for, flash
from flask_bootstrap import Bootstrap5
from flask_ckeditor import CKEditor
from flask_gravatar import Gravatar
from flask_login import UserMixin, login_user, LoginManager, current_user, logout_user
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship, DeclarativeBase, Mapped, mapped_column
from sqlalchemy import Integer, String, Text, ForeignKey
from functools import wraps
from werkzeug.security import generate_password_hash, check_password_hash
# Import your forms from the forms.py
from forms import CreatePostForm, RegisterForm, LoginForm
import os

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('FLASK_KEY')
ckeditor = CKEditor(app)
Bootstrap5(app)

# Configure Flask-Login
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return db.get_or_404(User, user_id)


# For adding profile images to the comment section
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

# CREATE DATABASE
class Base(DeclarativeBase):
    pass

app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DB_URI", "sqlite:///cafes.db")
db = SQLAlchemy(model_class=Base)
db.init_app(app)

# CONFIGURE TABLES
# Create a User table for all your registered users
class User(UserMixin, db.Model):
    __table_name__ = "user"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(100), unique=True)
    password: Mapped[str] = mapped_column(String(100))
    cafes: Mapped["Cafe"] = relationship(back_populates="user")

class Cafe(db.Model):
    __table_name__ = "cafes"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(250), unique=True, nullable=False)
    address: Mapped[str] = mapped_column(String(250), nullable=False)
    hours: Mapped[str] = mapped_column(String(250), nullable=False)
    location: Mapped[str] = mapped_column(Text, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("user.id"))
    user: Mapped["User"] = relationship(back_populates="cafes")


with app.app_context():
    db.create_all()


# Create an admin-only decorator
def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        # If id is not 1 then return abort with 403 error
        if current_user.id != 1:
            return abort(403)
        # Otherwise continue with the route function
        return f(*args, **kwargs)

    return decorated_function


# Register new users into the User database
@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()
    if form.validate_on_submit():

        # Check if user email is already present in the database.
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        user = result.scalar()
        if user:
            # User already exists
            flash("You've already signed up with that email, log in instead!")
            return redirect(url_for('login'))

        hash_and_salted_password = generate_password_hash(
            form.password.data,
            method='pbkdf2:sha256',
            salt_length=8
        )
        new_user = User(
            email=form.email.data,
            name=form.name.data,
            password=hash_and_salted_password,
        )
        db.session.add(new_user)
        db.session.commit()
        # This line will authenticate the user with Flask-Login
        login_user(new_user)
        return redirect(url_for('login'))
    return render_template("register.html", form=form, current_user=current_user)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()
    if form.validate_on_submit():
        password = form.password.data
        result = db.session.execute(db.select(User).where(User.email == form.email.data))
        # Note, email in db is unique so will only have one result.
        user = result.scalar()
        # Email doesn't exist
        if not user:
            flash("That email does not exist, please try again.")
            return redirect(url_for('login'))
        # Password incorrect
        elif not check_password_hash(user.password, password):
            flash('Password incorrect, please try again.')
            return redirect(url_for('login'))
        else:
            login_user(user)
            return redirect(url_for('add_new_cafe'))

    return render_template("login.html", form=form, current_user=current_user)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_cafes'))


@app.route('/')
def get_all_cafes():
    result = db.session.execute(db.select(Cafe))
    cafes = result.scalars().all()
    return render_template("index.html", all_cafes=cafes, current_user=current_user)




# Use a decorator so only an admin user can create new cafes
@app.route("/new-cafe", methods=["GET", "POST"])
def add_new_cafe():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_cafe = Cafe(
            name=form.name.data,
            hours=form.hours.data,
            address=form.address.data,
            location=form.location.data,
            user=current_user
        )
        db.session.add(new_cafe)
        db.session.commit()
        return redirect(url_for('thank_you'))
    return render_template("make-post.html", form=form, current_user=current_user)

# Use a decorator so only an admin user can edit a post
@app.route("/edit-cafe/<int:cafe_id>", methods=["GET", "POST"])
@admin_only
def edit_cafe(cafe_id):
    cafes = db.get_or_404(Cafe, cafe_id)
    edit_form = CreatePostForm(
        name=cafes.name,
        address=cafes.address,
        hours=cafes.hours,
        location=cafes.location,
    )

    if edit_form.validate_on_submit():
        cafes.name = edit_form.name.data
        cafes.address = edit_form.address.data
        cafes.hours = edit_form.hours.data
        cafes.location = edit_form.location.data
        db.session.commit()
        return redirect(url_for("show_post", cafes_id=cafes.id))
    return render_template("make-post.html", form=edit_form, is_edit=True, current_user=current_user)


# Use a decorator so only an admin user can delete a post
@app.route("/delete/<int:cafe_id>")
@admin_only
def delete_cafe(cafe_id):
    cafe_to_delete = db.get_or_404(Cafe, cafe_id)
    db.session.delete(cafe_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_cafes'))


@app.route("/cafes")
def cafes():
    return render_template("cafes.html", current_user=current_user)

@app.route("/thank-you")
def thank_you():
    return render_template("thank-you.html", current_user=current_user)



if __name__ == "__main__":
    app.run(debug=False, port=5001)