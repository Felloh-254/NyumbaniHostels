import time
import random
import string
import os
import pytz
import traceback
from flask import Blueprint, render_template, url_for, request, redirect, session, jsonify, flash, current_app, abort
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from PIL import Image
from app.db.db import get_db_connection, release_db_connection
from flask_login import login_user, logout_user, login_required, current_user
from datetime import datetime, timedelta
from app.__init__ import User
from functools import wraps


# Get the time as per the timezone
nairobi = pytz.timezone("Africa/Nairobi")
now = datetime.now(nairobi)

# Creating the blueprint
auth = Blueprint('auth', __name__, url_prefix='/')


def admin_required(view_func):
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            # Redirect to login or abort
            return current_app.login_manager.unauthorized()
        # Check if user has admin role
        conn = get_db_connection()
        try:
            cur = conn.cursor()
            cur.execute("""
                SELECT r.role_name
                FROM user_roles ur
                JOIN roles r ON ur.user_role_role_id = r.role_id
                WHERE ur.user_role_user_id = %s
            """, (current_user.id,))
            roles = [row[0] for row in cur.fetchall()]
            if "admin" not in roles:
                abort(403)  # Forbidden
        finally:
            cur.close()
            release_db_connection(conn)
        return view_func(*args, **kwargs)
    return decorated_view

def verified_required(view_func):
    @wraps(view_func)
    def decorated_view(*args, **kwargs):
        if not current_user.is_authenticated:
            return current_app.login_manager.unauthorized()
        return view_func(*args, **kwargs)
    return decorated_view


@auth.route('/login', methods=['GET', 'POST'])
def login():
    try:
        if request.method == 'POST' and request.is_json:
            data = request.get_json()
            email = data.get("email")
            password = data.get("password")

            conn = get_db_connection()
            if not conn:
                return jsonify({"message": "Database connection failed!"}), 400

            try:
                cur = conn.cursor()
                cur.execute(
                    '''SELECT user_id, user_password_hash, user_email, user_first_name, user_last_name,
                        user_gender, user_phone_number
                       FROM users
                       WHERE user_email = %s''',
                    (email,)
                )
                user_data = cur.fetchone()

                # If user not found or password is null
                if not user_data or not user_data[1]:
                    return jsonify({"message": "Invalid email or password!"}), 400

                if not check_password_hash(user_data[1], password):
                    return jsonify({"message": "Invalid email or password!"}), 400

                # Fetch user roles after successful password check
                cur.execute(
                    "SELECT user_role_role_id FROM user_roles WHERE user_role_user_id = %s",
                    (user_data[0],)
                )
                user_role = [role[0] for role in cur.fetchall()]

                if not user_role:
                    return jsonify({"message": "No role assigned. Please contact support!"}), 400

                # Log the user in
                user_id = user_data[0]
                user = User(user_id, user_data[2], user_data[3], user_data[4], user_data[5], user_data[6])
                login_user(user, remember=True)

                # Redirect based on role
                if 2 in user_role:
                    return jsonify({"redirect_url": "/admin/dashboard"}), 200
                elif 1 in user_role:
                    return jsonify({"redirect_url": "/student/dashboard"}), 200
                else:
                    return jsonify({"message": "Unknown role. Please contact support!"}), 400

            finally:
                cur.close()
                release_db_connection(conn)

        # For GET requests (page load)
        return render_template('/shared/login.html', user=current_user)
    except Exception as e:
        traceback.print_exc()




# Signup function
@auth.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.is_json:
        # Get data from the json
        user_info = request.get_json()
        user_email = user_info.get('email')
        user_first_name = user_info.get('firstName')
        user_last_name = user_info.get('lastName')
        user_gender = user_info.get('gender')
        user_phone_number = user_info.get('phone')
        profile_emergency_contact = user_info.get('emergencyContact')
        profile_student_id = user_info.get('studentId')
        user_password = user_info.get('password')

        # Check password length
        if len(user_password) < 8:
            return jsonify({"message": "Password length should not be less than 8"})

        if not user_email or not user_password or not user_first_name or not user_last_name:
            return jsonify({"message": "All fields are required"}), 400

        # Generate a password hash for our users
        hashed_password = generate_password_hash(user_password)

        # Establish a connection
        conn = get_db_connection()
        if not conn:
            return jsonify({"message": "Database connection failed!!"}), 400
        
        try:
            cur = conn.cursor()
            print("Inserting data...........")

            # Check if the user already exists
            cur.execute("SELECT user_id FROM users WHERE user_email = %s", (user_email,))
            if cur.fetchone():
                return jsonify({"message": "The email provided is already registered to an account"}), 400

            # Insert into users table
            cur.execute(
                '''INSERT INTO users
                (user_email, user_password_hash, user_first_name, user_last_name, user_phone_number,
                    user_gender)
                VALUES (%s, %s, %s, %s, %s, %s)
                RETURNING user_id''',
                (user_email, hashed_password, user_first_name, user_last_name, user_phone_number,
                    user_gender))

            user_id = cur.fetchone()[0]

            # Check if role exists
            cur.execute("SELECT role_id FROM roles WHERE role_id = 1")
            if not cur.fetchone():
                return jsonify({"message": "Default role not found in roles table!"}), 500

            # Get the default role
            cur.execute("SELECT role_id FROM roles WHERE role_name = 'student';")
            role_id = cur.fetchone()[0]

            # Insert into user_roles table
            cur.execute(
                '''INSERT INTO user_roles
                (user_role_user_id, user_role_role_id)
                VALUES (%s, %s);''',
                (user_id, role_id))


            # Insert into profiles table
            cur.execute('''
                INSERT INTO user_profile
                (profile_user_id, profile_emergency_contact, profile_student_id)
                VALUES (%s, %s, %s);
            ''', (user_id, profile_emergency_contact, profile_student_id))


            # Set session and commit
            session["user_id"] = user_id
            conn.commit()

            return jsonify({
                "redirect_url": url_for('auth.login'),
                "message": "Account created successfully! Redirecting..."
            }), 200
        except Exception as e:
            traceback.print_exc()
            print(f"Error during signup: {e}")

        finally:
            cur.close()
            release_db_connection(conn) 
    return render_template('/shared/signup.html')


@auth.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('shared.home'))
