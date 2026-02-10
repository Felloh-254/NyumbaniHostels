import os, psycopg2
from flask import Flask, Blueprint, render_template
from flask_bcrypt import Bcrypt
from dotenv import load_dotenv
from app.db.db import get_db_connection, release_db_connection
from flask_login import LoginManager, UserMixin
from bson.objectid import ObjectId
from collections import namedtuple

# Loading Environment variables
load_dotenv()

bcrypt = Bcrypt()

class User(UserMixin):
    def __init__(self, user_id, user_email, user_first_name, user_last_name, user_gender, user_phone_number, roles=None):
        self.id = user_id
        self.email = user_email
        self.first_name = user_first_name
        self.last_name = user_last_name
        self.gender = user_gender
        self.phone = user_phone_number
        self.roles = roles or []

    def get_id(self):
        return str(self.id)

    def has_role(self, role_name):
        return role_name in self.roles

def create_app():
	# Configuration of the Flask app
    app = Flask(__name__)
    app.config['SECRET_KEY'] = os.getenv("SECRET_KEY")

    # Create uploads folder if it doesn't exist
    UPLOAD_FOLDER = os.path.join(app.root_path, 'static', 'uploads')
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)

    app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
    app.config['MAX_CONTENT_LENGTH'] = 5 * 1024 * 1024


    # Register blueprints
    from .routes.auth import auth
    from .routes.shared import shared
    from .routes.admin import admin
    from .routes.student import student

    app.register_blueprint(auth)
    app.register_blueprint(shared)
    app.register_blueprint(admin)
    app.register_blueprint(student)

    bcrypt.init_app(app)

    # Seting up Flask-Login
    login_manager = LoginManager()
    login_manager.login_view = "auth.login"
    login_manager.init_app(app)

    @login_manager.user_loader
    def load_user(user_id):
        conn = get_db_connection()
        if not conn:
            print("Database connection failed!")
            return None

        try:
            cur = conn.cursor()

            # Get user details
            cur.execute('''
                SELECT user_id, user_email, user_first_name, user_last_name, user_gender,
                    user_phone_number
                FROM users WHERE user_id = %s;
            ''', (user_id,))
            user_data = cur.fetchone()

            if not user_data:
                return None

            # Get user roles
            cur.execute('''
                SELECT r.role_name FROM user_roles ur
                JOIN roles r ON ur.user_role_role_id = r.role_id
                WHERE ur.user_role_user_id = %s;
            ''', (user_id,))
            roles = [row[0] for row in cur.fetchall()]

            return User(*user_data, roles=roles)

        finally:
            cur.close()
            release_db_connection(conn)

    @app.errorhandler(Exception)
    def handle_all_errors(e):
        code = getattr(e, 'code', 500)

        error_titles = {
            400: "Oops — That request was bad",
            403: "Access denied — No sneaking in",
            404: "Oops — The page won't be found",
            500: "Uh-oh — Server’s having a meltdown",
        }

        error_messages = {
            400: "Your browser sent something my server couldn’t digest.",
            403: "Even the database says you’re not allowed here.",
            404: "Looks like the thing you were after took a detour into the void.",
            500: "I promise I didn’t trip over the cable… probably.",
        }

        fun_quotes = {
            400: "Don’t blame me — you clicked it.",
            403: "No entry — velvet ropes and all.",
            404: "Will you never leave me in peace? — 404's dramatic cry.",
            500: "Smoke is coming out of the server… metaphorically.",
        }

        return render_template(
            "/shared/error.html",
            code=code,
            title=error_titles.get(code, "An unexpected error occurred"),
            message=error_messages.get(code, "Something went wrong."),
            fun_quote=fun_quotes.get(code, "Drama intensifies.")
        ), code

    return app