from functools import wraps
from flask import Flask, render_template, redirect, url_for, flash, request, abort
from flask_bootstrap import Bootstrap
from flask_ckeditor import CKEditor
from datetime import date
import os
from dotenv import load_dotenv
from werkzeug.security import generate_password_hash, check_password_hash
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.orm import relationship
from flask_login import UserMixin, login_user, LoginManager, login_required, current_user, logout_user
from forms import CreatePostForm, RegisterForm, LoginForm, CommentForm
from flask_gravatar import Gravatar
load_dotenv()

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get("SECRET_KEY")
ckeditor = CKEditor(app)
Bootstrap(app)
gravatar = Gravatar(app,
                    size=100,
                    rating='g',
                    default='retro',
                    force_default=False,
                    force_lower=False,
                    use_ssl=False,
                    base_url=None)

##CONNECT TO DB
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get("DATABASE_URL")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
login_manager = LoginManager()
login_manager.init_app(app)


@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


def admin_only(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if current_user.id != 1:
            return abort(403, "Access denied")
        return f(*args, **kwargs)

    return decorated_function


##CONFIGURE TABLES

class BlogPost(db.Model):
    __tablename__ = "blog_posts"
    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    author = relationship("User", back_populates="post")
    title = db.Column(db.String(250), unique=True, nullable=False)
    subtitle = db.Column(db.String(250), nullable=False)
    date = db.Column(db.String(250), nullable=False)
    body = db.Column(db.Text, nullable=False)
    img_url = db.Column(db.String(250), nullable=False)
    comments = relationship("Comment", back_populates="parent_post")


class User(UserMixin, db.Model):
    __tablename__ = "users"
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(250), nullable=False)
    email = db.Column(db.String(250), unique=True, nullable=False)
    password = db.Column(db.String(250), nullable=False)
    post = relationship("BlogPost", back_populates="author")
    # "comment_author" refers to the comment_author property in the Comment class.
    comments = relationship("Comment", back_populates="comment_author")


class Comment(db.Model):
    __tablename__ = "comments"
    id = db.Column(db.Integer, primary_key=True)
    # "users.id" The users refers to the tablename of the Users class.

    author_id = db.Column(db.Integer, db.ForeignKey("users.id"))
    comment = db.Column(db.String(250), nullable=True)
    parent_post = relationship('BlogPost', back_populates="comments")
    post_id = db.Column(db.Integer, db.ForeignKey("blog_posts.id"))

    # "comments" refers to the comments property in the User class.
    comment_author = relationship("User", back_populates="comments")


db.create_all()


@app.route('/')
def get_all_posts():
    posts = BlogPost.query.all()
    # print(current_user.id)
    # admin = current_user.id
    return render_template("index.html", all_posts=posts, logging_user=current_user.is_authenticated,
                           admin=current_user)


@app.route('/register', methods=["GET", "POST"])
def register():
    form = RegisterForm()

    if form.validate_on_submit():
        user_exist = User.query.filter_by(email=request.form["email"]).first()
        if user_exist:
            flash("This user already exist")
            return redirect(url_for('login'))

        new_user = User()
        new_user.name = request.form["name"]
        new_user.email = request.form["email"]
        new_user.password = generate_password_hash(request.form["password"],
                                                   method='pbkdf2:sha256',
                                                   salt_length=8)
        print(new_user)
        db.session.add(new_user)
        db.session.commit()
        login_user(new_user)
        return redirect(url_for('get_all_posts'))

    return render_template("register.html", form=form)


@app.route('/login', methods=["GET", "POST"])
def login():
    form = LoginForm()

    if request.method == "POST":
        user = User.query.filter_by(email=request.form["email"]).first()
        # print(user.password)
        # print(generate_password_hash(request.form["password"], salt_length=8, method="pbkdf2:sha256"))
        user_password = request.form["password"]
        if not user:
            flash("User does not exist")
            return redirect(url_for('login'))

        elif check_password_hash(pwhash=user.password, password=user_password):
            login_user(user)
            return redirect(url_for('get_all_posts'))
        else:
            flash("You entered an Incorrect password")
            return redirect(url_for('login'))

    return render_template("login.html", form=form, logging_user=current_user.is_authenticated)


@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('get_all_posts'))


@app.route("/post/<int:post_id>", methods=["GET", "POST"])
def show_post(post_id):
    requested_post = BlogPost.query.get(post_id)
    comment = CommentForm()
    commenter = Comment.query.filter_by(post_id=post_id)
    comment_made = requested_post.comments

    if request.method == "POST":
        user_comment = request.form["comments"]
        if not current_user.is_authenticated:
            flash("User is not logged in")
            return redirect(url_for('login'))

        new_comment = Comment(author_id=current_user.id,
                              comment=user_comment,
                              post_id=post_id)
        db.session.add(new_comment)
        db.session.commit()

        return redirect(url_for('show_post', post_id=post_id))

    return render_template("post.html", post=requested_post, logging_user=current_user.is_authenticated,
                           admin=current_user, comment=comment, user_comment=comment_made, commenter=commenter)


@app.route("/about")
def about():
    return render_template("about.html", logging_user=current_user.is_authenticated, )


@app.route("/contact")
def contact():
    return render_template("contact.html", logging_user=current_user.is_authenticated)


@app.route("/new-post", methods=["GET", "POST"])
@admin_only
def add_new_post():
    form = CreatePostForm()
    if form.validate_on_submit():
        new_post = BlogPost(
            author_id=current_user.id,
            title=form.title.data,
            subtitle=form.subtitle.data,
            body=form.body.data,
            img_url=form.img_url.data,
            date=date.today().strftime("%B %d, %Y")
        )
        db.session.add(new_post)
        db.session.commit()
        return redirect(url_for("get_all_posts"))
    return render_template("make-post.html", form=form, logging_user=current_user.is_authenticated)


@app.route("/edit-post/<int:post_id>", methods=["GET", "POST"])
@admin_only
def edit_post(post_id):
    post = BlogPost.query.get(post_id)
    edit_form = CreatePostForm(
        title=post.title,
        subtitle=post.subtitle,
        img_url=post.img_url,
        body=post.body
    )
    if request.method == "POST":
        if edit_form.validate_on_submit():
            post.title = edit_form.title.data
            post.subtitle = edit_form.subtitle.data
            post.img_url = edit_form.img_url.data
            post.body = edit_form.body.data
            db.session.commit()
            return redirect(url_for("show_post", post_id=post.id))

    return render_template("make-post.html", form=edit_form, logging_user=current_user.is_authenticated)


@app.route("/delete/<int:post_id>")
@admin_only
def delete_post(post_id):
    post_to_delete = BlogPost.query.get(post_id)
    db.session.delete(post_to_delete)
    db.session.commit()
    return redirect(url_for('get_all_posts'))


if __name__ == "__main__":
    app.run(host='0.0.0.0', port=5000)
