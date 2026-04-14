from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_login import login_required, logout_user, login_user
from werkzeug.security import generate_password_hash, check_password_hash
from extensions import users_collection, User

auth_bp = Blueprint("auth", __name__)

# ==========================================================
# AUTH ROUTES
# ==========================================================

@auth_bp.route("/")
def home():
    return render_template("index.html")


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    return redirect(url_for("auth.home"))


@auth_bp.route("/login", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        user = users_collection.find_one({"username": username})

        if user and check_password_hash(user["password"], password):
            login_user(User(user))
            return redirect(url_for("dashboard.dashboard"))

        flash("Invalid username or password")

    return render_template("login.html")


@auth_bp.route("/signup", methods=["GET", "POST"])
def signup():

    if request.method == "POST":

        username = request.form["username"]
        password = request.form["password"]

        existing = users_collection.find_one({"username": username})

        if existing:
            flash("Username already exists")
            return redirect(url_for("auth.signup"))

        hashed_pw = generate_password_hash(password)

        users_collection.insert_one({
            "username": username,
            "password": hashed_pw,
            "role": "observer",
            "wallet": None,
            "approved": False
        })

        flash("Account created successfully", "success")
        return redirect(url_for("auth.login"))

    return render_template("signup.html")
