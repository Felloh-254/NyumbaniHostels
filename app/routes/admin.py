import os
import random
import string
import json
import io
import traceback
import psycopg2.extras
from psycopg2.extras import execute_values
from flask import Flask, render_template, url_for, request, jsonify, Blueprint, current_app, redirect, make_response, Response
from flask_login import login_user, logout_user, login_required, current_user
from app.db.db import get_db_connection, release_db_connection
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
from PIL import Image
from datetime import datetime, timedelta
from weasyprint import HTML
from .auth import admin_required

admin = Blueprint('admin', __name__, url_prefix='/')

############ ADMIN DASHBOARD ##################
@admin.route('/admin/dashboard')
@login_required
@admin_required
def dashboard():
    try:
        stats = get_dashboard_stats()
        recent_students = get_recent_students()
        return render_template(
            '/admin/dashboard.html',
            user=current_user,
            stats=stats,
            recent_students=recent_students
        )
    except Exception as e:
        print(f"Error in dashboard: {e}")


def calculate_percentage_change(current, previous):
    try:
        if previous == 0:
            return 100 if current > 0 else 0
        return round(((current - previous) / previous) * 100, 2)
    except:
        return 0

def get_dashboard_stats():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # --- Total Students ---
        try:
            cur.execute("SELECT COUNT(*) FROM users;")
            total_students = cur.fetchone()[0]
        except Exception as e:
            print(">>> Error in total students:", e)
            total_students = 0

        prev_students = total_students // 2
        total_students_change = calculate_percentage_change(total_students, prev_students)

        # --- Occupied Rooms ---
        try:
            cur.execute("SELECT COUNT(*) FROM bookings WHERE booking_status='Confirmed';")
            occupied_rooms = cur.fetchone()[0]
        except Exception as e:
            print(">>> Error in occupied rooms:", e)
            occupied_rooms = 0

        try:
            cur.execute("""
                SELECT COUNT(*) FROM bookings 
                WHERE booking_status='Confirmed'
                AND DATE_TRUNC('month', booking_date) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month');
            """)
            prev_occupied = cur.fetchone()[0]
        except Exception as e:
            print(">>> Error in prev occupied:", e)
            traceback.print_exc()
            prev_occupied = 0

        occupied_rooms_change = calculate_percentage_change(occupied_rooms, prev_occupied)

        # --- Pending Requests ---
        try:
            cur.execute("SELECT COUNT(*) FROM bookings WHERE booking_status='Pending';")
            pending_requests = cur.fetchone()[0]
        except Exception as e:
            print(">>> Error in pending:", e)
            pending_requests = 0

        try:
            cur.execute("""
                SELECT COUNT(*) FROM bookings 
                WHERE booking_status='Pending'
                AND DATE_TRUNC('month', booking_date) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month');
            """)
            prev_pending = cur.fetchone()[0]
        except Exception as e:
            print(">>> Error in prev pending:", e)
            prev_pending = 0

        pending_requests_change = calculate_percentage_change(pending_requests, prev_pending)

        # --- Monthly Revenue ---
        try:
            cur.execute("""
                SELECT COALESCE(SUM(payment_amount), 0)
                FROM payments 
                WHERE payment_status='Success'
                AND DATE_TRUNC('month', payment_date) = DATE_TRUNC('month', CURRENT_DATE);
            """)
            monthly_revenue = cur.fetchone()[0]
        except Exception as e:
            print(">>> Error in monthly revenue:", e)
            monthly_revenue = 0

        try:
            cur.execute("""
                SELECT COALESCE(SUM(payment_amount), 0)
                FROM payments 
                WHERE payment_status='Success'
                AND DATE_TRUNC('month', payment_date) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month');
            """)
            prev_revenue = cur.fetchone()[0]
        except Exception as e:
            print(">>> Error in prev revenue:", e)
            prev_revenue = 0

        monthly_revenue_change = calculate_percentage_change(monthly_revenue, prev_revenue)

        try:
            cur.execute("""
                SELECT 
                    TO_CHAR(DATE_TRUNC('month', b.booking_date), 'Mon') as month,
                    COUNT(*) as occupancy_count
                FROM bookings b
                WHERE b.booking_status = 'Confirmed'
                AND b.booking_date >= CURRENT_DATE - INTERVAL '6 months'
                GROUP BY DATE_TRUNC('month', b.booking_date)
                ORDER BY DATE_TRUNC('month', b.booking_date)
                LIMIT 6;
            """)
            occupancy_data = cur.fetchall()
            months = [row[0] for row in occupancy_data]
            occupancy_counts = [row[1] for row in occupancy_data]
        except Exception as e:
            print(">>> Error in occupancy chart data:", e)
            months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun']
            occupancy_counts = [0, 0, 0, 0, 0, 0]

        # Room status data
        try:
            cur.execute("""
                SELECT 
                    COUNT(*) as total_rooms,
                    COUNT(CASE WHEN b.booking_status = 'Confirmed' THEN 1 END) as occupied,
                    COUNT(CASE WHEN b.booking_status = 'Pending' THEN 1 END) as pending,
                    (SELECT COUNT(*) FROM rooms) - COUNT(CASE WHEN b.booking_status IN ('Confirmed', 'Pending') THEN 1 END) as available
                FROM bookings b
                WHERE b.booking_status IN ('Confirmed', 'Pending');
            """)
            room_stats = cur.fetchone()
            total_rooms = room_stats[0]
            occupied_rooms = room_stats[1]
            pending_rooms = room_stats[2]
            available_rooms = room_stats[3]
        except Exception as e:
            print(">>> Error in room status data:", e)
            total_rooms = occupied_rooms = pending_rooms = available_rooms = 0

        return {
            "total_students": total_students,
            "total_students_change": total_students_change,
            "occupied_rooms": occupied_rooms,
            "occupied_rooms_change": occupied_rooms_change,
            "pending_requests": pending_requests,
            "pending_requests_change": pending_requests_change,
            "monthly_revenue": monthly_revenue,
            "monthly_revenue_change": monthly_revenue_change,
            "chart_data": {
                "occupancy_months": months,
                "occupancy_counts": occupancy_counts,
                "room_status": {
                    "occupied": occupied_rooms,
                    "pending": pending_rooms,
                    "available": available_rooms
                }
            }
        }

    except Exception as e:
        print(">>> Fatal error in dashboard stats:", e)
        traceback.print_exc()
        return {
            "total_students": 0,
            "total_students_change": 0,
            "occupied_rooms": 0,
            "occupied_rooms_change": 0,
            "pending_requests": 0,
            "pending_requests_change": 0,
            "monthly_revenue": 0,
            "monthly_revenue_change": 0,
            "chart_data": {
                "occupancy_months": ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun'],
                "occupancy_counts": [0, 0, 0, 0, 0, 0],
                "room_status": {
                    "occupied": 0,
                    "pending": 0,
                    "available": 0
                }
            }
        }
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)



def get_recent_students(limit=5):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        cur.execute("""
            SELECT u.user_first_name, u.user_last_name, u.user_email, p.profile_student_id,
                r.room_number, a.allocation_date, b.booking_status
            FROM users u
            JOIN bookings b ON b.booking_user_id = u.user_id
            JOIN rooms r ON r.room_id = b.booking_room_id
            JOIN allocations a ON a.allocation_booking_id = b.booking_id
            JOIN user_profile p ON p.profile_user_id = u.user_id
            ORDER BY b.booking_date DESC
            LIMIT %s;
        """, (limit,))
        students = cur.fetchall()
        return students

    except Exception:
        traceback.print_exc()
        return []

    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)




################### Hostels & Rooms Management API Routes ##########################
@admin.route('/admin/rooms')
@login_required
@admin_required
def rooms():
    """Render the hostel rooms management page"""
    try:
        return render_template('/admin/hostel_rooms.html', user=current_user)
    except Exception as e:
        print(f"Error in rooms page: {e}")
        return "Error loading page", 500



@admin.route('/admin/get_hostels')
@login_required
@admin_required
def get_hostels():
    """Get all hostels from database"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT 
                h.hostel_id,
                h.hostel_name,
                h.hostel_location,
                h.hostel_total_rooms,
                h.hostel_description,
                h.hostel_image,
                COUNT(r.room_id) as total_rooms,
                COUNT(CASE WHEN b.booking_id IS NOT NULL AND b.booking_status = 'Confirmed' THEN 1 END) as occupied_rooms,
                (COUNT(r.room_id) - COUNT(CASE WHEN b.booking_id IS NOT NULL AND b.booking_status = 'Confirmed' THEN 1 END)) as available_rooms
            FROM hostels h
            LEFT JOIN rooms r ON h.hostel_id = r.room_hostel_id
            LEFT JOIN bookings b ON r.room_id = b.booking_room_id AND b.booking_status = 'Confirmed'
            GROUP BY h.hostel_id, h.hostel_name, h.hostel_location, h.hostel_total_rooms, h.hostel_description
            ORDER BY h.hostel_name;
        """)
        
        hostels = cur.fetchall()
        
        # Convert to list of dictionaries and calculate status
        hostel_list = []
        for hostel in hostels:
            hostel_dict = dict(hostel)
            hostel_dict['status'] = 'available' if hostel_dict['available_rooms'] > 0 else 'full'
            hostel_list.append(hostel_dict)
        
        return jsonify({
            'success': True,
            'hostels': hostel_list
        })
        
    except Exception as e:
        print(f"Error getting hostels: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Error fetching hostels data'
        }), 500
        
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@admin.route('/admin/get_rooms/<int:hostel_id>')
@login_required
@admin_required
def get_rooms(hostel_id):
    """Get all rooms for a specific hostel"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT 
                r.room_id,
                r.room_number,
                r.room_type,
                r.room_capacity,
                r.room_price_per_sem,
                CASE 
                    WHEN b.booking_id IS NOT NULL AND b.booking_status = 'Confirmed' THEN 'occupied'
                    ELSE 'available'
                END as status,
                COALESCE(array_agg(DISTINCT ri.image_url) FILTER (WHERE ri.image_url IS NOT NULL), '{}') as images
            FROM rooms r
            LEFT JOIN bookings b ON r.room_id = b.booking_room_id AND b.booking_status = 'Confirmed'
            LEFT JOIN room_images ri ON r.room_id = ri.image_room_id
            WHERE r.room_hostel_id = %s
            GROUP BY r.room_id, r.room_number, r.room_type, r.room_capacity, r.room_price_per_sem, b.booking_id, b.booking_status
            ORDER BY r.room_number;
        """, (hostel_id,))
        
        rooms = cur.fetchall()
        
        # Convert to list of dictionaries and add features
        room_list = []
        for room in rooms:
            room_dict = dict(room)
            room_dict['features'] = get_room_features(room_dict['room_type'])
            room_list.append(room_dict)
        
        return jsonify({
            'success': True,
            'rooms': room_list
        })
        
    except Exception as e:
        print(f"Error getting rooms: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Error fetching rooms data'
        }), 500
        
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

def get_room_features(room_type):
    """Get default features based on room type"""
    base_features = ["Study Desk", "WiFi"]
    
    if room_type == "Single":
        return ["Ensuite", "Single Bed"] + base_features
    elif room_type == "Double":
        return ["Ensuite", "Double Bed"] + base_features
    elif room_type == "Shared":
        return ["Shared Bathroom", "Bunk Beds"] + base_features
    else:
        return base_features

@admin.route('/admin/get_students')
@login_required
@admin_required
def get_students():
    """Get all students for room assignment"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        cur.execute("""
            SELECT 
                u.user_id,
                u.user_first_name,
                u.user_last_name,
                u.user_email,
                p.profile_student_id
            FROM users u
            JOIN user_profile p ON u.user_id = p.profile_user_id
            JOIN user_roles ur ON u.user_id = ur.user_role_user_id
            JOIN roles r ON ur.user_role_role_id = r.role_id
            WHERE r.role_name = 'student'
            AND u.user_id NOT IN (
                SELECT booking_user_id 
                FROM bookings 
                WHERE booking_status = 'Confirmed'
            )
            ORDER BY u.user_first_name, u.user_last_name;
        """)
        
        students = cur.fetchall()
        student_list = [dict(student) for student in students]
        
        return jsonify({
            'success': True,
            'students': student_list
        })
        
    except Exception as e:
        print(f"Error getting students: {e}")
        traceback.print_exc()
        return jsonify({
            'success': False,
            'message': 'Error fetching students data'
        }), 500
        
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@admin.route('/admin/add_room', methods=['POST'])
@login_required
@admin_required
def add_room():
    """Add a new room to a hostel"""
    conn = None
    cur = None
    try:
        hostel_id = request.form.get('hostel_id')
        room_number = request.form.get('room_number')
        room_type = request.form.get('room_type')
        room_capacity = request.form.get('room_capacity')
        room_price = request.form.get('room_price')
        
        # Validate required fields
        if not all([hostel_id, room_number, room_type, room_capacity, room_price]):
            return jsonify({
                'success': False,
                'message': 'All fields are required.'
            }), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if room number already exists in the same hostel
        cur.execute("""
            SELECT room_id FROM rooms 
            WHERE room_hostel_id = %s AND room_number = %s;
        """, (hostel_id, room_number))
        
        if cur.fetchone():
            return jsonify({
                'success': False,
                'message': 'Room number already exists in this hostel.'
            }), 400
        
        # Insert new room
        cur.execute("""
            INSERT INTO rooms (
                room_hostel_id, room_number, room_type, room_capacity, room_price_per_sem
            ) VALUES (%s, %s, %s, %s, %s)
            RETURNING room_id;
        """, (hostel_id, room_number, room_type, room_capacity, room_price))
        
        room_id = cur.fetchone()[0]
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Room added successfully!',
            'room_id': room_id
        })
        
    except Exception as e:
        print(f"Error adding room: {e}")
        traceback.print_exc()
        
        if conn:
            conn.rollback()
            
        return jsonify({
            'success': False,
            'message': 'Error adding room to database'
        }), 500
        
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@admin.route('/admin/assign_room', methods=['POST'])
@login_required
@admin_required
def assign_room():
    """Assign a room to a student"""
    conn = None
    cur = None
    try:
        room_id = request.form.get('room_id')
        student_id = request.form.get('student_id')
        booking_date = request.form.get('booking_date')
        vaccate_date = request.form.get('vaccate_date')
        
        # Validate required fields
        if not all([room_id, student_id, booking_date, vaccate_date]):
            return jsonify({
                'success': False,
                'message': 'All fields are required.'
            }), 400
        
        # Generate unique reference numbers
        booking_ref = f"BK{datetime.now().strftime('%Y%m%d%H%M%S')}"
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if room is already occupied
        cur.execute("""
            SELECT booking_id FROM bookings 
            WHERE booking_room_id = %s AND booking_status = 'Confirmed';
        """, (room_id,))
        
        if cur.fetchone():
            return jsonify({
                'success': False,
                'message': 'Room is already occupied.'
            }), 400
        
        # Check if student already has a confirmed booking
        cur.execute("""
            SELECT booking_id FROM bookings 
            WHERE booking_user_id = %s AND booking_status = 'Confirmed';
        """, (student_id,))
        
        if cur.fetchone():
            return jsonify({
                'success': False,
                'message': 'Student already has an assigned room.'
            }), 400

        # Check if the user has a balance needed in their account
        cur.execute("""
            SELECT profile_account_balance FROM user_profile
            WHERE profile_user_id = %s FOR UPDATE;
        """, (student_id,))

        balance=cur.fetchone()[0]

        # Get the room price
        cur.execute("""
            SELECT room_price_per_sem FROM rooms
            WHERE room_id = %s FOR UPDATE;
        """, (room_id,))
        room_data = cur.fetchone()
        if not room_data:
            conn.rollback()
            return jsonify({"success": False, "message": "Room not available"}), 404

        room_price = room_data[0]

        # Check balance
        if balance<room_price:
            conn.rollback()
            return jsonify({'success': False, 'message': 'Insufficient balance'}), 400

        # Deduct balance
        cur.execute("""
            UPDATE user_profile
            SET profile_account_balance=profile_account_balance-%s
            WHERE profile_user_id=%s
        """, (room_price, student_id))
        
        # Create booking
        cur.execute("""
            INSERT INTO bookings (
                booking_reference_number, booking_user_id, booking_room_id, booking_date, booking_status
            ) VALUES (%s, %s, %s, %s, 'Confirmed')
            RETURNING booking_id;
        """, (booking_ref, student_id, room_id, booking_date))
        
        booking_id = cur.fetchone()[0]
        
        # Create allocation
        cur.execute("""
            INSERT INTO allocations (
                allocation_booking_id, allocation_date, allocation_vaccate_date
            ) VALUES (%s, %s, %s);
        """, (booking_id, booking_date, vaccate_date))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Room assigned to student successfully!',
            'booking_ref': booking_ref
        })
        
    except Exception as e:
        print(f"Error assigning room: {e}")
        traceback.print_exc()
        
        if conn:
            conn.rollback()
            
        return jsonify({
            'success': False,
            'message': 'Error assigning room to student'
        }), 500
        
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@admin.route('/admin/add_hostel', methods=['POST'])
@login_required
@admin_required
def add_hostel():
    """Add a new hostel"""
    conn = None
    cur = None
    try:
        hostel_name = request.form.get('hostel_name')
        hostel_location = request.form.get('hostel_location')
        hostel_total_rooms = request.form.get('hostel_total_rooms')
        hostel_description = request.form.get('hostel_description')
        
        # Validate required fields
        if not all([hostel_name, hostel_location, hostel_total_rooms]):
            return jsonify({
                'success': False,
                'message': 'Hostel name, location, and total rooms are required.'
            }), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if hostel name already exists
        cur.execute("""
            SELECT hostel_id FROM hostels WHERE hostel_name = %s;
        """, (hostel_name,))
        
        if cur.fetchone():
            return jsonify({
                'success': False,
                'message': 'Hostel name already exists.'
            }), 400
        
        # Insert new hostel
        cur.execute("""
            INSERT INTO hostels (
                hostel_name, hostel_location, hostel_total_rooms, hostel_description
            ) VALUES (%s, %s, %s, %s)
            RETURNING hostel_id;
        """, (hostel_name, hostel_location, hostel_total_rooms, hostel_description))
        
        hostel_id = cur.fetchone()[0]
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Hostel added successfully!',
            'hostel_id': hostel_id
        })
        
    except Exception as e:
        print(f"Error adding hostel: {e}")
        traceback.print_exc()
        
        if conn:
            conn.rollback()
            
        return jsonify({
            'success': False,
            'message': 'Error adding hostel to database'
        }), 500
        
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

####################### BOOKINGS ############################
@admin.route('/admin/bookings')
@login_required
@admin_required
def bookings():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        booking_details = get_booking_details(cur)
        bookings_stats = get_bookings_stats(cur)
        
        return render_template('/admin/bookings.html', 
                             user=current_user,
                             bookings=booking_details,
                             stats=bookings_stats)
    except Exception as e:
        print(f"Error in bookings page: {e}")
        traceback.print_exc()
        return render_template('/admin/bookings.html', 
                             user=current_user,
                             bookings=[],
                             stats={})
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

def get_booking_details(cur):
    try:
        cur.execute("""
            SELECT 
                b.booking_id,
                b.booking_reference_number,
                b.booking_date,
                b.booking_status,
                u.user_first_name,
                u.user_last_name,
                u.user_email,
                u.user_phone_number,
                r.room_number,
                h.hostel_name,
                r.room_price_per_sem,
                a.allocation_date as check_in_date,
                a.allocation_vaccate_date as check_out_date,
                p.payment_status,
                p.payment_amount
            FROM bookings b
            JOIN users u ON u.user_id = b.booking_user_id
            JOIN rooms r ON r.room_id = b.booking_room_id
            JOIN hostels h ON h.hostel_id = r.room_hostel_id
            LEFT JOIN allocations a ON a.allocation_booking_id = b.booking_id
            LEFT JOIN payments p ON p.payment_id = a.allocation_payment_id
            ORDER BY b.booking_date DESC
            LIMIT 50;
        """)
        return cur.fetchall()
    except Exception as e:
        print(f"Error fetching booking details: {e}")
        return []

def get_bookings_stats(cur):
    try:
        # Current period stats (this month)
        cur.execute("""
            SELECT 
                COUNT(*) as total_bookings,
                COUNT(CASE WHEN booking_status = 'Confirmed' THEN 1 END) as confirmed_bookings,
                COUNT(CASE WHEN booking_status = 'Pending' THEN 1 END) as pending_bookings,
                COUNT(CASE WHEN booking_status = 'Cancelled' THEN 1 END) as cancelled_bookings
            FROM bookings 
            WHERE DATE_TRUNC('month', booking_date) = DATE_TRUNC('month', CURRENT_DATE);
        """)
        current_stats = cur.fetchone()
        
        # Previous period stats (last month)
        cur.execute("""
            SELECT 
                COUNT(*) as total_bookings,
                COUNT(CASE WHEN booking_status = 'Confirmed' THEN 1 END) as confirmed_bookings,
                COUNT(CASE WHEN booking_status = 'Pending' THEN 1 END) as pending_bookings,
                COUNT(CASE WHEN booking_status = 'Cancelled' THEN 1 END) as cancelled_bookings
            FROM bookings 
            WHERE DATE_TRUNC('month', booking_date) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month');
        """)
        previous_stats = cur.fetchone()
        
        # Calculate percentage changes
        def calculate_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 1)
        
        total_change = calculate_change(current_stats['total_bookings'], previous_stats['total_bookings'])
        confirmed_change = calculate_change(current_stats['confirmed_bookings'], previous_stats['confirmed_bookings'])
        pending_change = calculate_change(current_stats['pending_bookings'], previous_stats['pending_bookings'])
        cancelled_change = calculate_change(current_stats['cancelled_bookings'], previous_stats['cancelled_bookings'])
        
        return {
            "total_bookings": current_stats['total_bookings'],
            "total_change": total_change,
            "confirmed_bookings": current_stats['confirmed_bookings'],
            "confirmed_change": confirmed_change,
            "pending_bookings": current_stats['pending_bookings'],
            "pending_change": pending_change,
            "cancelled_bookings": current_stats['cancelled_bookings'],
            "cancelled_change": cancelled_change
        }
        
    except Exception as e:
        print(f"Error fetching bookings stats: {e}")
        return {
            "total_bookings": 0,
            "total_change": 0,
            "confirmed_bookings": 0,
            "confirmed_change": 0,
            "pending_bookings": 0,
            "pending_change": 0,
            "cancelled_bookings": 0,
            "cancelled_change": 0
        }


@admin.route('/admin/api/bookings/<int:booking_id>/status', methods=['PUT'])
@login_required
@admin_required
def update_booking_status(booking_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "UPDATE bookings SET booking_status = %s WHERE booking_id = %s",
            (new_status, booking_id)
        )
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Booking status updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)


################### Students ##########################
@admin.route('/admin/add_student', methods=['POST'])
@login_required
@admin_required
def add_student():
    """Add a new student account """
    conn = None
    cur = None
    try:
        # Get JSON data
        data = request.get_json()
        
        # Extract and validate required fields
        required_fields = ['firstName', 'lastName', 'email', 'studentId', 'password', 'gender']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'message': f'{field} is required'}), 400
        
        # Validate email format
        email = data['email'].strip().lower()
        if not email or '@' not in email:
            return jsonify({'success': False, 'message': 'Valid email is required'}), 400
        
        # Validate password length
        password = data['password']
        if len(password) < 8:
            return jsonify({'success': False, 'message': 'Password must be at least 8 characters'}), 400
        
        # Validate gender
        gender = data['gender']
        if gender not in ['Male', 'Female']:
            return jsonify({'success': False, 'message': 'Valid gender is required'}), 400
        
        # Validate status
        status = data.get('status', 'active')
        if status not in ['active', 'pending', 'inactive']:
            status = 'active'
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if email already exists
        cur.execute("SELECT user_id FROM users WHERE user_email = %s", (email,))
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'Email already registered'}), 400
        
        # Check if student ID already exists
        student_id = data['studentId'].strip()
        cur.execute("SELECT profile_id FROM user_profile WHERE profile_student_id = %s", (student_id,))
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'Student ID already exists'}), 400
                
        # Hash password
        hashed_password = generate_password_hash(password)
        
        # Insert into users table
        cur.execute("""
            INSERT INTO users (
                user_email, 
                user_password_hash, 
                user_first_name, 
                user_last_name, 
                user_phone_number,
                user_gender
            ) VALUES (%s, %s, %s, %s, %s, %s)
            RETURNING user_id
        """, (
            email,
            hashed_password,
            data['firstName'].strip(),
            data['lastName'].strip(),
            data.get('phone', '').strip(),
            gender
        ))
        
        user_id = cur.fetchone()[0]
        
        # Get the student role ID
        cur.execute("SELECT role_id FROM roles WHERE role_name = 'student'")
        role_result = cur.fetchone()
        
        if not role_result:
            conn.rollback()
            return jsonify({'success': False, 'message': 'Student role not found'}), 500
        
        role_id = role_result[0]
        
        # Insert into user_roles table
        cur.execute("""
            INSERT INTO user_roles (user_role_user_id, user_role_role_id)
            VALUES (%s, %s)
        """, (user_id, role_id))
        
        # Insert into user_profile table
        cur.execute("""
            INSERT INTO user_profile (
                profile_user_id,
                profile_student_id,
                profile_emergency_contact
            ) VALUES (%s, %s, %s)
        """, (
            user_id,
            student_id,
            data.get('emergencyContact', '').strip()
        ))
        
        # Commit transaction
        conn.commit()
        
        # Log the action
        current_app.logger.info(f'Admin {current_user.id} added student {user_id} ({email})')
        
        return jsonify({
            'success': True,
            'message': 'Student added successfully',
            'user_id': user_id,
            'student_id': student_id
        })
        
    except psycopg2.Error as e:
        if conn:
            conn.rollback()
        print(f"Database error adding student: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Database error occurred'}), 500
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error adding student: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An error occurred while adding student'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@admin.route('/admin/delete_student/<int:student_id>', methods=['DELETE'])
@login_required
@admin_required
def delete_student(student_id):
    """Delete a student account"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if student exists and is actually a student
        cur.execute("""
            SELECT u.user_id, u.user_first_name, u.user_last_name, u.user_email,
                   r.role_name
            FROM users u
            LEFT JOIN user_roles ur ON u.user_id = ur.user_role_user_id
            LEFT JOIN roles r ON ur.user_role_role_id = r.role_id
            WHERE u.user_id = %s AND r.role_name = 'student'
        """, (student_id,))
        
        student_data = cur.fetchone()
        if not student_data:
            return jsonify({'success': False, 'message': 'Student not found'}), 404
        
        # Check if student has active bookings
        cur.execute("""
            SELECT COUNT(*) as active_bookings
            FROM bookings 
            WHERE booking_user_id = %s 
            AND booking_status IN ('Confirmed', 'Pending')
        """, (student_id,))
        
        active_bookings = cur.fetchone()[0]
        if active_bookings > 0:
            return jsonify({
                'success': False, 
                'message': f'Cannot delete student with {active_bookings} active booking(s)'
            }), 400
        
        # Check if student has unpaid balance
        cur.execute("""
            SELECT profile_account_balance 
            FROM user_profile 
            WHERE profile_user_id = %s
        """, (student_id,))
        
        profile_result = cur.fetchone()
        if profile_result and profile_result[0] > 0:
            return jsonify({
                'success': False, 
                'message': 'Cannot delete student with account balance'
            }), 400
        
        # Start transaction
        conn.autocommit = False
        
        try:
            # Delete from dependent tables first
            # Delete from user_roles
            cur.execute("DELETE FROM user_roles WHERE user_role_user_id = %s", (student_id,))
            
            # Delete from user_profile
            cur.execute("DELETE FROM user_profile WHERE profile_user_id = %s", (student_id,))
            
            # Delete any related records
            # Delete from bookings
            cur.execute("DELETE FROM bookings WHERE booking_user_id = %s", (student_id,))
            
            # Delete from payments if linked
            cur.execute("""
                DELETE FROM payments 
                WHERE payment_reference_number IN (
                    SELECT booking_reference_number 
                    FROM bookings 
                    WHERE booking_user_id = %s
                )
            """, (student_id,))
            
            # Delete from users table
            cur.execute("DELETE FROM users WHERE user_id = %s", (student_id,))
            
            # Commit transaction
            conn.commit()
            
            # Log the action
            current_app.logger.info(f'Admin {current_user.id} deleted student {student_id}')
            
            return jsonify({
                'success': True,
                'message': 'Student deleted successfully'
            })
            
        except psycopg2.Error as e:
            conn.rollback()
            # If there are foreign key constraints, soft delete instead
            print(f"Hard delete failed, trying soft delete: {e}")
            
            # Perform soft delete (update status and anonymize email)
            cur.execute("""
                UPDATE users 
                SET user_status = 'inactive', 
                    user_email = CONCAT('deleted_', user_id, '_', user_email),
                    updated_at = NOW()
                WHERE user_id = %s
                RETURNING user_id
            """, (student_id,))
            
            conn.commit()
            
            return jsonify({
                'success': True,
                'message': 'Student deactivated successfully (soft delete)'
            })
            
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error deleting student: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'An error occurred while deleting student'}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

# Student management page (main view)
@admin.route('/admin/students')
@login_required
@admin_required
def manage_students():
    """Display student management page"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get pagination parameters
        page = request.args.get('page', 1, type=int)
        per_page = 20
        offset = (page - 1) * per_page
        
        # Get filter parameters
        search = request.args.get('search', '').strip()
        status_filter = request.args.get('status', 'all')
        sort_by = request.args.get('sort', 'newest')
        
        # Build query
        query = """
            SELECT 
                u.user_id,
                u.user_first_name,
                u.user_last_name,
                u.user_email,
                u.user_phone_number,
                u.user_gender,
                up.profile_student_id,
                up.profile_emergency_contact,
                up.profile_account_balance
            FROM users u
            INNER JOIN user_roles ur ON u.user_id = ur.user_role_user_id
            INNER JOIN roles r ON ur.user_role_role_id = r.role_id
            LEFT JOIN user_profile up ON u.user_id = up.profile_user_id
            WHERE r.role_name = 'student'
        """
        
        params = []
        
        # Apply search filter
        if search:
            query += """
                AND (u.user_first_name ILIKE %s 
                OR u.user_last_name ILIKE %s 
                OR u.user_email ILIKE %s
                OR up.profile_student_id ILIKE %s)
            """
            search_param = f"%{search}%"
            params.extend([search_param, search_param, search_param, search_param])
        
        # Apply sorting
        if sort_by == 'name_asc':
            query += " ORDER BY u.user_first_name, u.user_last_name"
        elif sort_by == 'name_desc':
            query += " ORDER BY u.user_first_name DESC, u.user_last_name DESC"
        else:
            query += " ORDER BY u.user_first_name, u.user_last_name"
        
        # Add pagination
        query += " LIMIT %s OFFSET %s"
        params.extend([per_page, offset])
        
        cur.execute(query, params)
        students = cur.fetchall()
        
        # Convert to list of dictionaries for template
        student_list = []
        for student in students:
            student_dict = {
                'user_id': student[0],
                'user_first_name': student[1],
                'user_last_name': student[2],
                'user_email': student[3],
                'user_phone_number': student[4],
                'user_gender': student[5],
                'profile_student_id': student[6],
                'profile_emergency_contact': student[7],
                'profile_account_balance': float(student[8]) if student[8] else 0.00
            }
            student_list.append(student_dict)
        
        # Get statistics
        stats_query = """
            SELECT 
                COUNT(*) as total_students
            FROM users u
            INNER JOIN user_roles ur ON u.user_id = ur.user_role_user_id
            INNER JOIN roles r ON ur.user_role_role_id = r.role_id
            WHERE r.role_name = 'student'
        """
        
        cur.execute(stats_query)
        stats_row = cur.fetchone()
        
        stats = {
            'total_students': stats_row[0] if stats_row else 0
        }
        
        return render_template('admin/users.html',
                             students=student_list,
                             stats=stats,
                             current_page=page,
                             user=current_user)
        
    except Exception as e:
        print(f"Error in manage_students: {str(e)}")
        traceback.print_exc()
        return render_template('admin/users.html',
                             students=[],
                             stats={'total_students': 0, 'active_students': 0, 'pending_students': 0, 'inactive_students': 0},
                             current_page=1,
                             user=current_user)
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)


################ PAYMENTS ######################
@admin.route('/admin/payments')
@login_required
@admin_required
def payments():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        payment_details = get_payment_details(cur)
        payments_stats = get_payments_stats(cur)
        
        return render_template('/admin/payment.html', 
                             user=current_user,
                             payments=payment_details,
                             stats=payments_stats)
    except Exception as e:
        print(f"Error in payments page: {e}")
        return render_template('/admin/payment.html', 
                             user=current_user,
                             payments=[],
                             stats={})
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

def get_payment_details(cur):
    try:
        cur.execute("""
            SELECT 
                p.payment_id,
                p.payment_reference_number,
                p.payment_amount,
                p.payment_method,
                p.payment_date,
                p.payment_status,
                u.user_first_name,
                u.user_last_name,
                u.user_email,
                b.booking_reference_number,
                r.room_number,
                h.hostel_name
            FROM payments p
            LEFT JOIN allocations a ON a.allocation_payment_id = p.payment_id
            LEFT JOIN bookings b ON b.booking_id = a.allocation_booking_id
            LEFT JOIN users u ON u.user_id = b.booking_user_id
            LEFT JOIN rooms r ON r.room_id = b.booking_room_id
            LEFT JOIN hostels h ON h.hostel_id = r.room_hostel_id
            ORDER BY p.payment_date DESC
            LIMIT 50;
        """)
        return cur.fetchall()
    except Exception as e:
        print(f"Error fetching payment details: {e}")
        return []

def get_payments_stats(cur):
    try:
        # Current period stats (this month)
        cur.execute("""
            SELECT 
                COUNT(*) as total_payments,
                COALESCE(SUM(payment_amount), 0) as total_revenue,
                COUNT(CASE WHEN payment_status = 'Success' THEN 1 END) as successful_payments,
                COUNT(CASE WHEN payment_status = 'Pending' THEN 1 END) as pending_payments,
                COUNT(CASE WHEN payment_status = 'Failed' THEN 1 END) as failed_payments,
                COALESCE(SUM(CASE WHEN payment_status = 'Success' THEN payment_amount ELSE 0 END), 0) as successful_revenue
            FROM payments 
            WHERE DATE_TRUNC('month', payment_date) = DATE_TRUNC('month', CURRENT_DATE);
        """)
        current_stats = cur.fetchone()
        
        # Previous period stats (last month)
        cur.execute("""
            SELECT 
                COUNT(*) as total_payments,
                COALESCE(SUM(payment_amount), 0) as total_revenue,
                COUNT(CASE WHEN payment_status = 'Success' THEN 1 END) as successful_payments,
                COUNT(CASE WHEN payment_status = 'Pending' THEN 1 END) as pending_payments,
                COUNT(CASE WHEN payment_status = 'Failed' THEN 1 END) as failed_payments,
                COALESCE(SUM(CASE WHEN payment_status = 'Success' THEN payment_amount ELSE 0 END), 0) as successful_revenue
            FROM payments 
            WHERE DATE_TRUNC('month', payment_date) = DATE_TRUNC('month', CURRENT_DATE - INTERVAL '1 month');
        """)
        previous_stats = cur.fetchone()
        
        # All-time totals for display
        cur.execute("""
            SELECT 
                COUNT(*) as total_payments,
                COALESCE(SUM(payment_amount), 0) as total_revenue,
                COUNT(CASE WHEN payment_status = 'Success' THEN 1 END) as successful_payments,
                COUNT(CASE WHEN payment_status = 'Pending' THEN 1 END) as pending_payments,
                COUNT(CASE WHEN payment_status = 'Failed' THEN 1 END) as failed_payments,
                COALESCE(SUM(CASE WHEN payment_status = 'Success' THEN payment_amount ELSE 0 END), 0) as successful_revenue
            FROM payments;
        """)
        all_time_stats = cur.fetchone()
        
        # Calculate percentage changes
        def calculate_change(current, previous):
            if previous == 0:
                return 100 if current > 0 else 0
            return round(((current - previous) / previous) * 100, 1)
        
        total_payments_change = calculate_change(current_stats['total_payments'], previous_stats['total_payments'])
        total_revenue_change = calculate_change(current_stats['total_revenue'], previous_stats['total_revenue'])
        successful_change = calculate_change(current_stats['successful_payments'], previous_stats['successful_payments'])
        pending_change = calculate_change(current_stats['pending_payments'], previous_stats['pending_payments'])
        failed_change = calculate_change(current_stats['failed_payments'], previous_stats['failed_payments'])
        
        return {
            "total_payments": all_time_stats['total_payments'],
            "total_payments_change": total_payments_change,
            "total_revenue": all_time_stats['total_revenue'],
            "total_revenue_change": total_revenue_change,
            "successful_payments": all_time_stats['successful_payments'],
            "successful_change": successful_change,
            "pending_payments": all_time_stats['pending_payments'],
            "pending_change": pending_change,
            "failed_payments": all_time_stats['failed_payments'],
            "failed_change": failed_change,
            "successful_revenue": all_time_stats['successful_revenue']
        }
        
    except Exception as e:
        print(f"Error fetching payments stats: {e}")
        return {
            "total_payments": 0,
            "total_payments_change": 0,
            "total_revenue": 0,
            "total_revenue_change": 0,
            "successful_payments": 0,
            "successful_change": 0,
            "pending_payments": 0,
            "pending_change": 0,
            "failed_payments": 0,
            "failed_change": 0,
            "successful_revenue": 0
        }


@admin.route('/admin/api/payments/<int:payment_id>/status', methods=['PUT'])
@login_required
@admin_required
def update_payment_status(payment_id):
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        cur.execute(
            "UPDATE payments SET payment_status = %s WHERE payment_id = %s",
            (new_status, payment_id)
        )
        
        conn.commit()
        return jsonify({'success': True, 'message': 'Payment status updated successfully'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)


################# SUPPORT ######################
@admin.route('/admin/support')
@login_required
@admin_required
def support():
    try:
        support_categories = [
            {
                'title': 'Booking Help',
                'icon': 'booking',
                'questions': [
                    'How to make a booking?',
                    'How to cancel a booking?',
                    'Booking status meanings',
                    'Room selection guide'
                ]
            },
            {
                'title': 'Payment Help',
                'icon': 'payment',
                'questions': [
                    'Payment methods accepted',
                    'Payment failed issues',
                    'Refund process',
                    'Payment confirmation'
                ]
            },
            {
                'title': 'Account Help',
                'icon': 'account',
                'questions': [
                    'How to update profile?',
                    'Password reset',
                    'Account verification',
                    'Contact information update'
                ]
            },
            {
                'title': 'Technical Support',
                'icon': 'technical',
                'questions': [
                    'Website issues',
                    'Mobile app problems',
                    'Login difficulties',
                    'Browser compatibility'
                ]
            }
        ]
        
        return render_template('/admin/support.html', 
                             user=current_user,
                             categories=support_categories)
    except Exception as e:
        print(f"Error in support page: {e}")
        return render_template('/admin/support.html', 
                             user=current_user,
                             categories=[])


################# SETTINGS SECTION ####################### 
@admin.route('/admin/settings')
@login_required
@admin_required
def settings():
    return render_template('/admin/settings.html', user = current_user)



@admin.route('/admin/update_profile', methods=['POST'])
@login_required
@admin_required
def update_profile():
    """Update user profile information"""
    conn = None
    cur = None
    try:
        # Get form data
        first_name = request.form.get('firstName', '').strip()
        last_name = request.form.get('lastName', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        bio = request.form.get('bio', '').strip()
        
        # Validate required fields
        if not first_name or not last_name or not email:
            return jsonify({
                'success': False,
                'message': 'First name, last name, and email are required.'
            }), 400
        
        # Validate email format
        if '@' not in email:
            return jsonify({
                'success': False,
                'message': 'Please enter a valid email address.'
            }), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Check if email already exists for another user
        cur.execute("""
            SELECT user_id FROM users 
            WHERE user_email = %s AND user_id != %s;
        """, (email, current_user.id))
        
        if cur.fetchone():
            return jsonify({
                'success': False,
                'message': 'Email address is already in use by another account.'
            }), 400
        
        # Update users table
        cur.execute("""
            UPDATE users 
            SET user_first_name = %s, 
                user_last_name = %s, 
                user_email = %s, 
                user_phone_number = %s,
                user_description = %s
            WHERE user_id = %s;
        """, (first_name, last_name, email, phone, bio, current_user.id))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully!'
        })
        
    except Exception as e:
        print(f"Error updating profile: {e}")
        traceback.print_exc()
        
        if conn:
            conn.rollback()
            
        return jsonify({
            'success': False,
            'message': 'An error occurred while updating your profile. Please try again.'
        }), 500
        
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@admin.route('/admin/change_password', methods=['POST'])
@login_required
@admin_required
def change_password():
    """Change user password"""
    conn = None
    cur = None
    try:
        current_password = request.form.get('currentPassword', '').strip()
        new_password = request.form.get('newPassword', '').strip()
        confirm_password = request.form.get('confirmPassword', '').strip()
        
        # Validate inputs
        if not current_password or not new_password or not confirm_password:
            return jsonify({
                'success': False,
                'message': 'All password fields are required.'
            }), 400
        
        if new_password != confirm_password:
            return jsonify({
                'success': False,
                'message': 'New password and confirmation do not match.'
            }), 400
        
        if len(new_password) < 6:
            return jsonify({
                'success': False,
                'message': 'New password must be at least 6 characters long.'
            }), 400
        
        conn = get_db_connection()
        cur = conn.cursor()
        
        # Get current password hash
        cur.execute("""
            SELECT user_password_hash FROM users 
            WHERE user_id = %s;
        """, (current_user.id,))
        
        result = cur.fetchone()
        if not result:
            return jsonify({
                'success': False,
                'message': 'User not found.'
            }), 404
        
        current_password_hash = result[0]
        
        if not verify_password(current_password, current_password_hash):
            return jsonify({
                'success': False,
                'message': 'Current password is incorrect.'
            }), 400
        
        # Hash new password
        new_password_hash = hash_password(new_password)
        
        # Update password
        cur.execute("""
            UPDATE users 
            SET user_password_hash = %s
            WHERE user_id = %s;
        """, (new_password_hash, current_user.id))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Password changed successfully!'
        })
        
    except Exception as e:
        print(f"Error changing password: {e}")
        traceback.print_exc()
        
        if conn:
            conn.rollback()
            
        return jsonify({
            'success': False,
            'message': 'An error occurred while changing your password. Please try again.'
        }), 500
        
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

# Helper functions for password handling
def verify_password(plain_password, hashed_password):
    """Verify a password against its hash using werkzeug.security"""
    try:
        return check_password_hash(hashed_password, plain_password)
    except Exception as e:
        print(f"Error verifying password: {e}")
        return False

def hash_password(password):
    """Hash a password using werkzeug.security"""
    try:
        return generate_password_hash(password)
    except Exception as e:
        print(f"Error hashing password: {e}")
        # Fallback
        return generate_password_hash(password)




################## REPORTS ########################
@admin.route('/admin/reports')
@login_required
@admin_required
def reports():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        reports_data = get_reports_data(cur)
        charts_data = get_charts_data(cur)
        
        return render_template('/admin/reports.html', 
                             user=current_user,
                             reports=reports_data,
                             charts=charts_data)
    except Exception as e:
        print(f"Error in reports page: {e}")
        return render_template('/admin/reports.html', 
                             user=current_user,
                             reports={},
                             charts={})
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

def get_reports_data(cur):
    try:
        cur.execute("""
            SELECT 
                -- Booking statistics
                (SELECT COUNT(*) FROM bookings) as total_bookings,
                (SELECT COUNT(*) FROM bookings WHERE booking_status = 'Confirmed') as confirmed_bookings,
                (SELECT COUNT(*) FROM bookings WHERE booking_status = 'Pending') as pending_bookings,
                (SELECT COUNT(*) FROM bookings WHERE booking_status = 'Cancelled') as cancelled_bookings,
                
                -- Payment statistics
                (SELECT COUNT(*) FROM payments) as total_payments,
                (SELECT COUNT(*) FROM payments WHERE payment_status = 'Success') as successful_payments,
                (SELECT COUNT(*) FROM payments WHERE payment_status = 'Pending') as pending_payments,
                (SELECT COUNT(*) FROM payments WHERE payment_status = 'Failed') as failed_payments,
                (SELECT COALESCE(SUM(payment_amount), 0) FROM payments WHERE payment_status = 'Success') as total_revenue,
                
                -- Room statistics
                (SELECT COUNT(*) FROM rooms) as total_rooms,
                (SELECT COUNT(DISTINCT booking_room_id) FROM bookings WHERE booking_status = 'Confirmed') as occupied_rooms,
                (SELECT COUNT(*) FROM users) as total_users,
                
                -- Recent activity
                (SELECT COUNT(*) FROM bookings WHERE booking_date >= CURRENT_DATE - INTERVAL '7 days') as weekly_bookings,
                (SELECT COALESCE(SUM(payment_amount), 0) FROM payments WHERE payment_date >= CURRENT_DATE - INTERVAL '30 days' AND payment_status = 'Success') as monthly_revenue,
                
                -- Gender distribution
                (SELECT COUNT(*) FROM users WHERE user_gender = 'Male') as male_users,
                (SELECT COUNT(*) FROM users WHERE user_gender = 'Female') as female_users,
                
                -- Room type distribution
                (SELECT COUNT(*) FROM rooms WHERE room_type = 'Single') as single_rooms,
                (SELECT COUNT(*) FROM rooms WHERE room_type = 'Double') as double_rooms,
                (SELECT COUNT(*) FROM rooms WHERE room_type = 'Shared') as shared_rooms,
                
                -- Performance metrics
                (SELECT AVG(payment_amount) FROM payments WHERE payment_status = 'Success') as avg_booking_value,
                (SELECT COUNT(*) FROM bookings WHERE booking_date = CURRENT_DATE) as today_bookings
        """)
        return cur.fetchone()
    except Exception as e:
        print(f"Error fetching reports data: {e}")
        return {}

def get_charts_data(cur):
    try:
        # Monthly booking trends
        cur.execute("""
            SELECT 
                TO_CHAR(booking_date, 'Mon') as month,
                COUNT(*) as booking_count
            FROM bookings 
            WHERE booking_date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY TO_CHAR(booking_date, 'Mon'), DATE_TRUNC('month', booking_date)
            ORDER BY DATE_TRUNC('month', booking_date)
            LIMIT 6;
        """)
        booking_trends = cur.fetchall()
        
        # Hostel distribution
        cur.execute("""
            SELECT 
                h.hostel_name,
                COUNT(b.booking_id) as booking_count,
                COUNT(DISTINCT r.room_id) as total_rooms,
                COALESCE(SUM(p.payment_amount), 0) as total_revenue
            FROM hostels h
            LEFT JOIN rooms r ON r.room_hostel_id = h.hostel_id
            LEFT JOIN bookings b ON b.booking_room_id = r.room_id AND b.booking_status = 'Confirmed'
            LEFT JOIN payments p ON p.payment_reference_number = b.booking_reference_number AND p.payment_status = 'Success'
            GROUP BY h.hostel_id, h.hostel_name
            ORDER BY total_revenue DESC;
        """)
        hostel_stats = cur.fetchall()
        
        # Payment method distribution
        cur.execute("""
            SELECT 
                payment_method,
                COUNT(*) as payment_count,
                SUM(payment_amount) as total_amount
            FROM payments 
            WHERE payment_status = 'Success'
            GROUP BY payment_method;
        """)
        payment_methods = cur.fetchall()
        
        # Booking status distribution
        cur.execute("""
            SELECT 
                booking_status,
                COUNT(*) as status_count
            FROM bookings 
            GROUP BY booking_status;
        """)
        booking_statuses = cur.fetchall()
        
        # Monthly revenue trends
        cur.execute("""
            SELECT 
                TO_CHAR(payment_date, 'Mon') as month,
                COALESCE(SUM(payment_amount), 0) as revenue
            FROM payments 
            WHERE payment_status = 'Success' 
            AND payment_date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY TO_CHAR(payment_date, 'Mon'), DATE_TRUNC('month', payment_date)
            ORDER BY DATE_TRUNC('month', payment_date)
            LIMIT 6;
        """)
        revenue_trends = cur.fetchall()
        
        # Recent bookings
        cur.execute("""
            SELECT 
                b.booking_reference_number,
                u.user_first_name,
                u.user_last_name,
                r.room_number,
                b.booking_date,
                b.booking_status
            FROM bookings b
            JOIN users u ON b.booking_user_id = u.user_id
            JOIN rooms r ON b.booking_room_id = r.room_id
            ORDER BY b.booking_date DESC
            LIMIT 10;
        """)
        recent_bookings = cur.fetchall()
        
        return {
            'booking_trends': booking_trends,
            'hostel_stats': hostel_stats,
            'payment_methods': payment_methods,
            'booking_statuses': booking_statuses,
            'revenue_trends': revenue_trends,
            'recent_bookings': recent_bookings
        }
    except Exception as e:
        print(f"Error fetching charts data: {e}")
        return {
            'booking_trends': [],
            'hostel_stats': [],
            'payment_methods': [],
            'booking_statuses': [],
            'revenue_trends': [],
            'recent_bookings': []
        }

@admin.route('/admin/reports/export/pdf')
@login_required
@admin_required
def export_reports_pdf():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        reports_data = get_reports_data(cur)
        charts_data = get_charts_data(cur)
        
        # Generate comprehensive PDF
        html_content = render_template('/admin/reports_pdf.html',
                                     reports=reports_data,
                                     charts=charts_data,
                                     generated_at=datetime.now())
        
        # Create PDF
        pdf_file = HTML(string=html_content, base_url=os.path.dirname(__file__)).write_pdf()
        
        cur.close()
        release_db_connection(conn)
        
        return Response(
            pdf_file,
            mimetype='application/pdf',
            headers={
                'Content-Disposition': 'attachment; filename=hostel_comprehensive_report.pdf',
                'Content-Type': 'application/pdf'
            }
        )
    except Exception as e:
        print(f"Error generating PDF: {e}")
        return "Error generating PDF report", 500



@admin.route('/admin/reports/export/csv')
@login_required
@admin_required
def export_reports_csv():
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        reports_data = get_reports_data(cur)
        charts_data = get_charts_data(cur)
        
        # Generate comprehensive CSV
        csv_content = []
        csv_content.append("HOSTEL MANAGEMENT SYSTEM - COMPREHENSIVE REPORT")
        csv_content.append(f"Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        csv_content.append("")
        
        # Key Statistics
        csv_content.append("KEY STATISTICS")
        csv_content.append(f"Total Revenue,Ksh {reports_data.get('total_revenue', 0):.2f}")
        csv_content.append(f"Monthly Revenue,Ksh {reports_data.get('monthly_revenue', 0):.2f}")
        csv_content.append(f"Total Users,{reports_data.get('total_users', 0)}")
        csv_content.append(f"Total Bookings,{reports_data.get('total_bookings', 0)}")
        csv_content.append(f"Confirmed Bookings,{reports_data.get('confirmed_bookings', 0)}")
        csv_content.append("")
        
        # Booking Statistics
        csv_content.append("BOOKING STATISTICS")
        csv_content.append("Status,Count")
        for status in charts_data.get('booking_statuses', []):
            csv_content.append(f"{status['booking_status']},{status['status_count']}")
        csv_content.append("")
        
        # Revenue Breakdown
        csv_content.append("REVENUE BREAKDOWN")
        csv_content.append("Period,Revenue")
        for revenue in charts_data.get('revenue_trends', []):
            csv_content.append(f"{revenue['month']},Ksh {revenue['revenue']:.2f}")
        csv_content.append("")
        
        # Hostel Performance
        csv_content.append("HOSTEL PERFORMANCE")
        csv_content.append("Hostel,Bookings,Total Rooms,Revenue")
        for hostel in charts_data.get('hostel_stats', []):
            csv_content.append(f"{hostel['hostel_name']},{hostel['booking_count']},{hostel['total_rooms']},Ksh {hostel['total_revenue']:.2f}")
        
        csv_output = "\n".join(csv_content)
        
        cur.close()
        release_db_connection(conn)
        
        return Response(
            csv_output,
            mimetype='text/csv',
            headers={
                'Content-Disposition': 'attachment; filename=hostel_comprehensive_report.csv',
                'Content-Type': 'text/csv'
            }
        )
    except Exception as e:
        print(f"Error generating CSV: {e}")
        return "Error generating CSV report", 500