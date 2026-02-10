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
from PIL import Image
from datetime import datetime, timedelta
from weasyprint import HTML

student = Blueprint('student', __name__, url_prefix='/')


######################## DASHBOARD ###########################
@student.route('/student/dashboard')
@login_required
def student_dashboard():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        user_id = current_user.id
        
        # Get student statistics
        stats = get_student_stats(cur, user_id)
        
        # Get recent bookings
        recent_bookings = get_recent_bookings(cur, user_id)
        
        return render_template('/student/dashboard.html', 
                             user=current_user,
                             stats=stats,
                             recent_bookings=recent_bookings)
    except Exception as e:
        print(f"Error in student dashboard: {e}")
        return render_template('/student/dashboard.html', 
                             user=current_user,
                             stats={},
                             recent_bookings=[])
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

def get_student_stats(cur, user_id):
    try:
        # Get current booking info
        cur.execute("""
            SELECT 
                b.booking_id,
                b.booking_status,
                r.room_number,
                h.hostel_name,
                r.room_price_per_sem,
                a.allocation_date,
                a.allocation_vaccate_date
            FROM bookings b
            LEFT JOIN rooms r ON b.booking_room_id = r.room_id
            LEFT JOIN hostels h ON r.room_hostel_id = h.hostel_id
            LEFT JOIN allocations a ON a.allocation_booking_id = b.booking_id
            WHERE b.booking_user_id = %s 
            AND b.booking_status IN ('Confirmed', 'Pending')
            ORDER BY b.booking_date DESC
            LIMIT 1
        """, (user_id,))
        current_booking = cur.fetchone()
        
        # Get payment status and balance
        cur.execute("""
            SELECT 
                COALESCE(SUM(p.payment_amount), 0) as total_paid,
                (SELECT COALESCE(SUM(r.room_price_per_sem), 0) 
                 FROM bookings b 
                 JOIN rooms r ON b.booking_room_id = r.room_id 
                 WHERE b.booking_user_id = %s AND b.booking_status = 'Confirmed') as total_due
            FROM payments p
            JOIN bookings b ON p.payment_reference_number = b.booking_reference_number
            WHERE b.booking_user_id = %s AND p.payment_status = 'Success'
        """, (user_id, user_id))
        payment_info = cur.fetchone()
        
        # Calculate days remaining
        days_remaining = 0
        if current_booking and current_booking.get('allocation_vaccate_date'):
            vaccate_date = current_booking['allocation_vaccate_date']
            if isinstance(vaccate_date, str):
                vaccate_date = datetime.strptime(vaccate_date, '%Y-%m-%d').date()
            days_remaining = (vaccate_date - datetime.now().date()).days
            days_remaining = max(0, days_remaining)
        
        # Get pending notifications count
        cur.execute("""
            SELECT COUNT(*) as pending_count
            FROM bookings 
            WHERE booking_user_id = %s 
            AND booking_status = 'Pending'
        """, (user_id,))
        pending_notifications = cur.fetchone()['pending_count']
        
        # Get chart data
        chart_data = get_student_chart_data(cur, user_id)
        
        return {
            'current_booking': current_booking['room_number'] + ' - ' + current_booking['hostel_name'] if current_booking else None,
            'booking_status': current_booking['booking_status'] if current_booking else 'No Booking',
            'balance_due': payment_info['total_due'] - payment_info['total_paid'] if payment_info else 0,
            'payment_status': 'Paid' if payment_info and payment_info['total_paid'] >= payment_info['total_due'] else 'Pending',
            'days_remaining': days_remaining,
            'pending_notifications': pending_notifications,
            'chart_data': chart_data
        }
    except Exception as e:
        print(f"Error fetching student stats: {e}")
        return {}

def get_student_chart_data(cur, user_id):
    try:
        # Payment history for last 6 months
        cur.execute("""
            SELECT 
                TO_CHAR(p.payment_date, 'Mon') as month,
                COALESCE(SUM(p.payment_amount), 0) as amount
            FROM payments p
            JOIN bookings b ON p.payment_reference_number = b.booking_reference_number
            WHERE b.booking_user_id = %s 
            AND p.payment_status = 'Success'
            AND p.payment_date >= CURRENT_DATE - INTERVAL '6 months'
            GROUP BY TO_CHAR(p.payment_date, 'Mon'), DATE_TRUNC('month', p.payment_date)
            ORDER BY DATE_TRUNC('month', p.payment_date)
            LIMIT 6
        """, (user_id,))
        payment_data = cur.fetchall()
        
        # Booking status distribution
        cur.execute("""
            SELECT 
                booking_status,
                COUNT(*) as count
            FROM bookings 
            WHERE booking_user_id = %s
            GROUP BY booking_status
        """, (user_id,))
        booking_status_data = cur.fetchall()
        
        # Format data for charts
        payment_months = [item['month'] for item in payment_data]
        payment_amounts = [float(item['amount']) for item in payment_data]
        
        booking_status = {
            'confirmed': 0,
            'pending': 0,
            'cancelled': 0
        }
        for item in booking_status_data:
            status = item['booking_status'].lower()
            if status in booking_status:
                booking_status[status] = item['count']
        
        return {
            'payment_months': payment_months,
            'payment_amounts': payment_amounts,
            'booking_status': booking_status
        }
    except Exception as e:
        print(f"Error fetching chart data: {e}")
        return {
            'payment_months': [],
            'payment_amounts': [],
            'booking_status': {'confirmed': 0, 'pending': 0, 'cancelled': 0}
        }

def get_recent_bookings(cur, user_id):
    try:
        cur.execute("""
            SELECT 
                b.booking_id,
                b.booking_reference_number,
                b.booking_date,
                b.booking_status,
                r.room_number,
                r.room_price_per_sem,
                h.hostel_name
            FROM bookings b
            JOIN rooms r ON b.booking_room_id = r.room_id
            JOIN hostels h ON r.room_hostel_id = h.hostel_id
            WHERE b.booking_user_id = %s
            ORDER BY b.booking_date DESC
            LIMIT 5
        """, (user_id,))
        return cur.fetchall()
    except Exception as e:
        print(f"Error fetching recent bookings: {e}")
        return []



######################### ROOMS #############################
@student.route('/student/rooms')
@login_required
def available_rooms():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get query parameters for filtering
        page = request.args.get('page', 1, type=int)
        hostel_id = request.args.get('hostel', '')
        room_type = request.args.get('type', '')
        price_min = request.args.get('price_min', '')
        price_max = request.args.get('price_max', '')
        capacity = request.args.get('capacity', '')
        search = request.args.get('search', '')
        
        # Build query for available rooms
        query = """
            SELECT DISTINCT
                r.room_id,
                r.room_number,
                r.room_type,
                r.room_capacity,
                r.room_price_per_sem,
                h.hostel_id,
                h.hostel_name,
                h.hostel_location,
                h.hostel_description,
                (r.room_capacity - COALESCE((
                    SELECT COUNT(*) 
                    FROM bookings b 
                    WHERE b.booking_room_id = r.room_id
                    AND b.booking_status IN ('Confirmed', 'Pending')
                ), 0)) AS spots_left
            FROM rooms r
            JOIN hostels h ON r.room_hostel_id = h.hostel_id
            WHERE (r.room_capacity - COALESCE((
                SELECT COUNT(*) 
                FROM bookings b 
                WHERE b.booking_room_id = r.room_id
                AND b.booking_status IN ('Confirmed', 'Pending')
            ), 0)) > 0
        """
        
        params = []
        
        # Additional filters
        if hostel_id:
            query += " AND h.hostel_id = %s"
            params.append(hostel_id)
        
        if room_type:
            query += " AND r.room_type = %s"
            params.append(room_type)
        
        if price_min:
            query += " AND r.room_price_per_sem >= %s"
            params.append(float(price_min))
        
        if price_max:
            query += " AND r.room_price_per_sem <= %s"
            params.append(float(price_max))
        
        if capacity:
            query += " AND r.room_capacity = %s"
            params.append(int(capacity))
        
        if search:
            query += " AND (r.room_number ILIKE %s OR h.hostel_name ILIKE %s OR h.hostel_location ILIKE %s)"
            params.extend([f'%{search}%', f'%{search}%', f'%{search}%'])
        
        # Add ordering
        query += " ORDER BY r.room_price_per_sem ASC, h.hostel_name, r.room_number"
        
        # Execute query
        cur.execute(query, params)
        rooms = cur.fetchall()
                
        # Get room images
        for room in rooms:
            cur.execute("""
                SELECT image_url FROM room_images 
                WHERE image_room_id = %s 
                ORDER BY image_id
            """, (room['room_id'],))
            room['images'] = cur.fetchall()
        
        # Get hostels for filter dropdown
        cur.execute("SELECT hostel_id, hostel_name FROM hostels ORDER BY hostel_name")
        hostels = cur.fetchall()
        
        # Calculate pagination
        per_page = 12
        total_rooms = len(rooms)
        total_pages = (total_rooms + per_page - 1) // per_page
        
        # Apply pagination
        start_idx = (page - 1) * per_page
        end_idx = start_idx + per_page
        paginated_rooms = rooms[start_idx:end_idx]
        
        # Get notifications count
        notifications_count = get_student_notifications_count(cur, current_user.id)
        
        return render_template('/student/rooms.html',
                             user=current_user,
                             rooms=paginated_rooms,
                             hostels=hostels,
                             current_page=page,
                             total_pages=total_pages,
                             notifications_count=notifications_count)
    except Exception as e:
        print(f"Error in available rooms: {e}")
        import traceback
        traceback.print_exc()
        return render_template('/student/rooms.html',
                             user=current_user,
                             rooms=[],
                             hostels=[],
                             current_page=1,
                             total_pages=1,
                             notifications_count=0)
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

def get_student_notifications_count(cur, user_id):
    """Get count of pending notifications for student"""
    try:
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM bookings 
            WHERE booking_user_id = %s 
            AND booking_status = 'Pending'
        """, (user_id,))
        result = cur.fetchone()
        return result['count'] if result else 0
    except Exception as e:
        print(f"Error getting notifications count: {e}")
        return 0

@student.route('/student/bookings/create', methods=['POST'])
@login_required
def create_booking():
    """Create a new booking for a room"""
    conn = None
    cur = None
    try:
        data = request.get_json()
        room_id = data.get('room_id')
        user_id = current_user.id
        
        if not room_id:
            return jsonify({'success': False, 'message': 'Room ID is required'})
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Check if room is available
        cur.execute("BEGIN;")
        cur.execute("""
            SELECT r.room_id
            FROM rooms r
            WHERE r.room_id = %s
            AND (
                SELECT COUNT(*) 
                FROM bookings b
                WHERE b.booking_room_id = r.room_id
                AND b.booking_status IN ('Confirmed', 'Pending')
            ) < r.room_capacity
            FOR UPDATE
        """, (room_id,))
        
        if not cur.fetchone():
            return jsonify({'success': False, 'message': 'Room is not available'})
        
        # Check if user already has a pending or confirmed booking
        cur.execute("""
            SELECT b.booking_id
            FROM bookings b
            LEFT JOIN allocations a ON a.allocation_booking_id = b.booking_id
            WHERE b.booking_user_id = %s
            AND (
                b.booking_status = 'Pending'
                OR (b.booking_status = 'Confirmed' AND a.allocation_vaccate_date > CURRENT_DATE)
            )
        """, (user_id,))
        
        if cur.fetchone():
            return jsonify({'success': False, 'message': 'You already have an active booking'})
        
        # Generate unique reference number
        import uuid
        reference_number = f"BK{uuid.uuid4().hex[:8].upper()}"

        # Fetch room price
        cur.execute("SELECT room_price_per_sem FROM rooms WHERE room_id = %s", (room_id,))
        room = cur.fetchone()
        if not room:
            conn.rollback()
            return jsonify({'success': False, 'message': 'Room not found'})
        room_price = room['room_price_per_sem']

        # Fetch user balance
        cur.execute("""
            SELECT profile_account_balance 
            FROM user_profile 
            WHERE profile_user_id = %s
            FOR UPDATE
        """, (user_id,))
        profile = cur.fetchone()
        if not profile:
            conn.rollback()
            return jsonify({'success': False, 'message': 'User profile not found'})

        user_balance = profile['profile_account_balance']

        # If not enough balance, create only booking and exit
        if user_balance < room_price:
            cur.execute("""
                INSERT INTO bookings (booking_reference_number, booking_user_id, booking_room_id, booking_status)
                VALUES (%s, %s, %s, 'Pending')
                RETURNING booking_id
            """, (reference_number, user_id, room_id))
            
            booking_id = cur.fetchone()['booking_id']
            conn.commit()

            return jsonify({
                'success': True,
                'message': 'Booking created but not confirmed. Insufficient balance.',
                'booking_id': booking_id,
                'reference_number': reference_number
            })

        # Otherwise user can pay → deduct balance
        new_balance = user_balance - room_price
        cur.execute("""
            UPDATE user_profile
            SET profile_account_balance = %s
            WHERE profile_user_id = %s
        """, (new_balance, user_id))

        # Create payment record
        payment_ref = f"PM{uuid.uuid4().hex[:8].upper()}"
        cur.execute("""
            INSERT INTO payments (payment_reference_number, payment_amount, payment_method, payment_status)
            VALUES (%s, %s, 'Mpesa', 'Success')
            RETURNING payment_id
        """, (payment_ref, room_price))
        payment_id = cur.fetchone()['payment_id']

        # Create booking as confirmed
        cur.execute("""
            INSERT INTO bookings (booking_reference_number, booking_user_id, booking_room_id, booking_status)
            VALUES (%s, %s, %s, 'Confirmed')
            RETURNING booking_id
        """, (reference_number, user_id, room_id))
        booking_id = cur.fetchone()['booking_id']

        # Create allocation
        cur.execute("""
            INSERT INTO allocations (allocation_booking_id, allocation_payment_id, allocation_vaccate_date)
            VALUES (%s, %s, CURRENT_DATE + INTERVAL '120 days')
        """, (booking_id, payment_id))

        conn.commit()

        return jsonify({
            'success': True,
            'message': 'Booking confirmed and room allocated successfully.',
            'booking_id': booking_id,
            'reference_number': reference_number,
            'payment_reference': payment_ref
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error creating booking: {e}")
        traceback.print_exc()
        return jsonify({'success': False, 'message': 'Error creating booking'})
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)


@student.route('/student/rooms/<int:room_id>')
@login_required
def room_details(room_id):
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get room details with availability info
        cur.execute("""
            SELECT 
                r.room_id,
                r.room_number,
                r.room_type,
                r.room_capacity,
                r.room_price_per_sem,
                h.hostel_id,
                h.hostel_name,
                h.hostel_location,
                h.hostel_description,
                CASE 
                    WHEN EXISTS (
                        SELECT 1 FROM bookings b 
                        WHERE b.booking_room_id = r.room_id 
                        AND b.booking_status IN ('Confirmed', 'Pending')
                    ) THEN false 
                    ELSE true 
                END as is_available
            FROM rooms r
            JOIN hostels h ON r.room_hostel_id = h.hostel_id
            WHERE r.room_id = %s
        """, (room_id,))
        
        room = cur.fetchone()
        
        if not room:
            flash('Room not found', 'error')
            return redirect(url_for('student.available_rooms'))
        
        # Get all room images
        cur.execute("""
            SELECT image_url FROM room_images 
            WHERE image_room_id = %s 
            ORDER BY image_id
        """, (room_id,))
        room_images = cur.fetchall()
        
        # Get similar rooms (same hostel, different room)
        cur.execute("""
            SELECT 
                r.room_id,
                r.room_number,
                r.room_type,
                r.room_price_per_sem,
                r.room_capacity
            FROM rooms r
            WHERE r.room_hostel_id = %s 
            AND r.room_id != %s
            AND NOT EXISTS (
                SELECT 1 FROM bookings b 
                WHERE b.booking_room_id = r.room_id 
                AND b.booking_status IN ('Confirmed', 'Pending')
            )
            ORDER BY r.room_price_per_sem ASC
            LIMIT 4
        """, (room['hostel_id'], room_id))
        similar_rooms = cur.fetchall()
        
        # Get notifications count
        notifications_count = get_student_notifications_count(cur, current_user.id)
        
        return render_template('/student/room_details.html',
                             user=current_user,
                             room=room,
                             room_images=room_images,
                             similar_rooms=similar_rooms,
                             notifications_count=notifications_count)
    except Exception as e:
        print(f"Error in room details: {e}")
        import traceback
        traceback.print_exc()
        flash('Error loading room details', 'error')
        return redirect(url_for('student.available_rooms'))
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)



######################### BOOKINGS #####################
@student.route('/student/bookings')
@login_required
def my_bookings():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        user_id = current_user.id
        status_filter = request.args.get('status', 'all')
        
        # Build query based on status filter
        query = """
            SELECT 
                b.booking_id,
                b.booking_reference_number,
                b.booking_date,
                b.booking_status,
                r.room_number,
                r.room_type,
                r.room_capacity,
                r.room_price_per_sem,
                h.hostel_name,
                h.hostel_location,
                a.allocation_date,
                a.allocation_vaccate_date,
                p.payment_status,
                p.payment_amount,
                p.payment_date
            FROM bookings b
            JOIN rooms r ON b.booking_room_id = r.room_id
            JOIN hostels h ON r.room_hostel_id = h.hostel_id
            LEFT JOIN allocations a ON a.allocation_booking_id = b.booking_id
            LEFT JOIN payments p ON p.payment_id = a.allocation_payment_id
            WHERE b.booking_user_id = %s
        """
        
        params = [user_id]
        
        # Apply status filter
        if status_filter != 'all':
            if status_filter == 'completed':
                query += " AND (b.booking_status = 'Completed' OR a.allocation_vaccate_date < CURRENT_DATE)"
            else:
                query += " AND b.booking_status = %s"
                params.append(status_filter.capitalize())
        
        query += " ORDER BY b.booking_date DESC"
        
        cur.execute(query, params)
        bookings = cur.fetchall()
        
        # Calculate days remaining for confirmed bookings
        for booking in bookings:
            if booking['allocation_vaccate_date'] and booking['booking_status'] == 'Confirmed':
                vaccate_date = booking['allocation_vaccate_date']
                if isinstance(vaccate_date, str):
                    vaccate_date = datetime.strptime(vaccate_date, '%Y-%m-%d').date()
                days_remaining = (vaccate_date - datetime.now().date()).days
                booking['days_remaining'] = max(0, days_remaining)
        
        # Get notifications count
        notifications_count = get_student_notifications_count(cur, user_id)
        
        return render_template('/student/bookings.html',
                             user=current_user,
                             bookings=bookings,
                             notifications_count=notifications_count)
    except Exception as e:
        print(f"Error in my bookings: {e}")
        return render_template('/student/bookings.html',
                             user=current_user,
                             bookings=[],
                             notifications_count=0)
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@student.route('/student/bookings/<int:booking_id>/cancel', methods=['POST'])
@login_required
def cancel_booking(booking_id):
    conn = None
    cur = None
    try:
        user_id = current_user.id
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Verify booking belongs to user and is cancellable
        cur.execute("""
            SELECT booking_id, booking_status 
            FROM bookings 
            WHERE booking_id = %s AND booking_user_id = %s
        """, (booking_id, user_id))
        
        booking = cur.fetchone()
        
        if not booking:
            return jsonify({'success': False, 'message': 'Booking not found'})
        
        if booking['booking_status'] not in ['Pending', 'Confirmed']:
            return jsonify({'success': False, 'message': 'Booking cannot be cancelled'})
        
        # Update booking status to cancelled
        cur.execute("""
            UPDATE bookings 
            SET booking_status = 'Cancelled' 
            WHERE booking_id = %s
        """, (booking_id,))
        
        conn.commit()
        
        return jsonify({'success': True, 'message': 'Booking cancelled successfully'})
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error cancelling booking: {e}")
        return jsonify({'success': False, 'message': 'Error cancelling booking'})
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)


def get_student_notifications_count(cur, user_id):
    """Get count of pending notifications for student"""
    try:
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM bookings 
            WHERE booking_user_id = %s 
            AND booking_status = 'Pending'
        """, (user_id,))
        result = cur.fetchone()
        return result['count'] if result else 0
    except Exception as e:
        print(f"Error getting notifications count: {e}")
        return 0


########################## PAYMENT ########################
@student.route('/student/payments')
@login_required
def make_payment():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        user_id = current_user.id
        booking_id = request.args.get('booking_id')
        
        booking = None
        if booking_id:
            # Get booking details
            cur.execute("""
                SELECT 
                    b.booking_id,
                    b.booking_reference_number,
                    b.booking_status,
                    r.room_number,
                    r.room_type,
                    r.room_price_per_sem,
                    h.hostel_name
                FROM bookings b
                JOIN rooms r ON b.booking_room_id = r.room_id
                JOIN hostels h ON r.room_hostel_id = h.hostel_id
                WHERE b.booking_id = %s AND b.booking_user_id = %s
            """, (booking_id, user_id))
            booking = cur.fetchone()
        
        # Get user's current account balance
        cur.execute("""
            SELECT profile_account_balance 
            FROM user_profile 
            WHERE profile_user_id = %s
        """, (user_id,))
        profile = cur.fetchone()
        account_balance = profile['profile_account_balance'] if profile else 0.00
        
        # Get notifications count
        notifications_count = get_student_notifications_count(cur, user_id)
        
        return render_template('/student/make_payment.html',
                             user=current_user,
                             booking=booking,
                             account_balance=account_balance,
                             notifications_count=notifications_count)
    except Exception as e:
        print(f"Error in make payment: {e}")
        return render_template('/student/make_payment.html',
                             user=current_user,
                             booking=None,
                             account_balance=0.00,
                             notifications_count=0)
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@student.route('/student/payments/process', methods=['POST'])
@login_required
def process_payment():
    conn = None
    cur = None
    try:
        user_id = current_user.id
        payment_method = request.form.get('payment_method')
        booking_id = request.form.get('booking_id')
        amount = request.form.get('amount')
        
        if not amount or float(amount) <= 0:
            return jsonify({'success': False, 'message': 'Valid amount is required'})
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Verify booking belongs to user if provided
        booking = None
        if booking_id:
            cur.execute("""
                SELECT booking_id, booking_reference_number, booking_status 
                FROM bookings 
                WHERE booking_id = %s AND booking_user_id = %s
            """, (booking_id, user_id))
            booking = cur.fetchone()
            
            if not booking:
                return jsonify({'success': False, 'message': 'Booking not found'})
            
            if booking['booking_status'] not in ['Pending', 'Confirmed']:
                return jsonify({'success': False, 'message': 'Cannot process payment for this booking'})
        
        # Generate payment reference
        import uuid
        payment_reference = f"PY{uuid.uuid4().hex[:8].upper()}"
        
        if payment_method == 'mpesa':
            # Process M-Pesa payment
            phone_number = request.form.get('phone_number')
            
            # M-Pesa API to be integrated here
            # For now, we'll simulate successful payment
            cur.execute("""
                INSERT INTO payments (payment_reference_number, payment_amount, payment_method, payment_status)
                VALUES (%s, %s, 'Mpesa', 'Success')
                RETURNING payment_id
            """, (payment_reference, amount))
            
            payment_status = 'Success'
            
        else:  # manual payment
            manual_method = request.form.get('manual_payment_method')
            transaction_ref = request.form.get('transaction_reference')
            payment_date = request.form.get('payment_date')
            
            # Handle file upload
            receipt_file = None
            if 'receipt' in request.files:
                file = request.files['receipt']
                if file and file.filename:
                    filename = f"receipt_{payment_reference}_{file.filename}"
                    file_path = os.path.join(current_app.config['UPLOAD_FOLDER'], filename)
                    file.save(file_path)
                    receipt_file = file_path
            
            cur.execute("""
                INSERT INTO payments (payment_reference_number, payment_amount, payment_method, payment_status, payment_date, payment_receipt)
                VALUES (%s, %s, %s, 'Pending', %s, %s)
                RETURNING payment_id
            """, (payment_reference, amount, manual_method, payment_date, receipt_file))
            
            payment_status = 'Success'
        
        payment_result = cur.fetchone()
        payment_id = payment_result['payment_id']
        
        # Update user's account balance
        cur.execute("""
            UPDATE user_profile 
            SET profile_account_balance = profile_account_balance + %s
            WHERE profile_user_id = %s
        """, (amount, user_id))
        
        # If payment is successful and there's a booking, update booking status
        if payment_status == 'Success' and booking:
            cur.execute("""
                UPDATE bookings 
                SET booking_status = 'Confirmed' 
                WHERE booking_id = %s
            """, (booking_id,))
            
            # Create allocation if booking is confirmed
            if booking['booking_status'] == 'Pending':
                import datetime
                allocation_date = datetime.date.today()
                vaccate_date = allocation_date + datetime.timedelta(days=120)  # 4 months for a semester
                
                cur.execute("""
                    INSERT INTO allocations (allocation_booking_id, allocation_payment_id, allocation_date, allocation_vaccate_date)
                    VALUES (%s, %s, %s, %s)
                """, (booking_id, payment_id, allocation_date, vaccate_date))
        
        conn.commit()
        
        return jsonify({
            'success': True, 
            'message': 'Payment processed successfully',
            'payment_id': payment_id,
            'reference': payment_reference,
            'new_balance': get_user_balance(cur, user_id)
        })
        
    except Exception as e:
        if conn:
            conn.rollback()
        print(f"Error processing payment: {e}")
        return jsonify({'success': False, 'message': 'Error processing payment'})
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@student.route('/student/payments/history')
@login_required
def payment_history():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        user_id = current_user.id
        
        # Get payment history (including payments without bookings)
        cur.execute("""
            SELECT 
                p.payment_id,
                p.payment_reference_number,
                p.payment_amount,
                p.payment_method,
                p.payment_status,
                p.payment_date,
                p.payment_receipt,
                b.booking_reference_number,
                r.room_number,
                h.hostel_name,
                up.profile_account_balance
            FROM payments p
            LEFT JOIN bookings b ON p.payment_reference_number = b.booking_reference_number
            LEFT JOIN rooms r ON b.booking_room_id = r.room_id
            LEFT JOIN hostels h ON r.room_hostel_id = h.hostel_id
            LEFT JOIN user_profile up ON up.profile_user_id = %s
            WHERE EXISTS (
                SELECT 1 FROM bookings 
                WHERE booking_user_id = %s 
                AND booking_reference_number = p.payment_reference_number
            ) OR p.payment_id IN (
                SELECT payment_id FROM payments 
                WHERE payment_reference_number LIKE 'PY%'
            )
            ORDER BY p.payment_date DESC
        """, (user_id, user_id))
        
        payments = cur.fetchall()
        
        # Get current account balance
        cur.execute("""
            SELECT profile_account_balance 
            FROM user_profile 
            WHERE profile_user_id = %s
        """, (user_id,))
        profile = cur.fetchone()
        account_balance = profile['profile_account_balance'] if profile else 0.00
        
        # Get notifications count
        notifications_count = get_student_notifications_count(cur, user_id)
        
        return render_template('/student/payment_history.html',
                             user=current_user,
                             payments=payments,
                             account_balance=account_balance,
                             notifications_count=notifications_count)
    except Exception as e:
        print(f"Error in payment history: {e}")
        return render_template('/student/payment_history.html',
                             user=current_user,
                             payments=[],
                             account_balance=0.00,
                             notifications_count=0)
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

def get_user_balance(cur, user_id):
    """Get user's current account balance"""
    try:
        cur.execute("""
            SELECT profile_account_balance 
            FROM user_profile 
            WHERE profile_user_id = %s
        """, (user_id,))
        result = cur.fetchone()
        return float(result['profile_account_balance']) if result else 0.00
    except Exception as e:
        print(f"Error getting user balance: {e}")
        return 0.00

def get_student_notifications_count(cur, user_id):
    """Get count of pending notifications for student"""
    try:
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM bookings 
            WHERE booking_user_id = %s 
            AND booking_status = 'Pending'
        """, (user_id,))
        result = cur.fetchone()
        return result['count'] if result else 0
    except Exception as e:
        print(f"Error getting notifications count: {e}")
        return 0




################### PAYMMENT-HISTORY ##################
@student.route('/student/payments/payment-history')
@login_required
def student_payment_history():
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        user_id = current_user.id
        status_filter = request.args.get('status', 'all')
        
        # Build query based on status filter
        query = """
            SELECT 
                p.payment_id,
                p.payment_reference_number,
                p.payment_amount,
                p.payment_method,
                p.payment_status,
                p.payment_date,
                b.booking_reference_number,
                r.room_number,
                h.hostel_name
            FROM payments p
            JOIN bookings b ON p.payment_reference_number = b.booking_reference_number
            JOIN rooms r ON b.booking_room_id = r.room_id
            JOIN hostels h ON r.room_hostel_id = h.hostel_id
            WHERE b.booking_user_id = %s
        """
        
        params = [user_id]
        
        # Apply status filter
        if status_filter != 'all':
            query += " AND p.payment_status = %s"
            params.append(status_filter.capitalize())
        
        query += " ORDER BY p.payment_date DESC"
        
        cur.execute(query, params)
        payments = cur.fetchall()
        
        # Calculate payment statistics
        stats = get_payment_statistics(cur, user_id)
        
        # Get notifications count
        notifications_count = get_student_notifications_count(cur, user_id)
        
        return render_template('/student/payment_history.html',
                             user=current_user,
                             payments=payments,
                             stats=stats,
                             notifications_count=notifications_count)
    except Exception as e:
        print(f"Error in payment history: {e}")
        return render_template('/student/payment_history.html',
                             user=current_user,
                             payments=[],
                             stats={},
                             notifications_count=0)
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

def get_payment_statistics(cur, user_id):
    """Calculate payment statistics for the student"""
    try:
        # Total paid amount
        cur.execute("""
            SELECT COALESCE(SUM(payment_amount), 0) as total_paid
            FROM payments p
            JOIN bookings b ON p.payment_reference_number = b.booking_reference_number
            WHERE b.booking_user_id = %s AND p.payment_status = 'Success'
        """, (user_id,))
        total_paid = cur.fetchone()['total_paid']
        
        # Count by status
        cur.execute("""
            SELECT 
                COUNT(*) as total_transactions,
                SUM(CASE WHEN payment_status = 'Success' THEN 1 ELSE 0 END) as successful_payments,
                SUM(CASE WHEN payment_status = 'Pending' THEN 1 ELSE 0 END) as pending_payments,
                SUM(CASE WHEN payment_status = 'Failed' THEN 1 ELSE 0 END) as failed_payments
            FROM payments p
            JOIN bookings b ON p.payment_reference_number = b.booking_reference_number
            WHERE b.booking_user_id = %s
        """, (user_id,))
        counts = cur.fetchone()
        
        return {
            'total_paid': float(total_paid),
            'total_transactions': counts['total_transactions'],
            'successful_payments': counts['successful_payments'],
            'pending_payments': counts['pending_payments'],
            'failed_payments': counts['failed_payments']
        }
    except Exception as e:
        print(f"Error getting payment statistics: {e}")
        return {
            'total_paid': 0,
            'total_transactions': 0,
            'successful_payments': 0,
            'pending_payments': 0,
            'failed_payments': 0
        }

@student.route('/student/payments/<int:payment_id>')
@login_required
def payment_details(payment_id):
    conn = None
    cur = None
    try:
        user_id = current_user.id
        
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get detailed payment information
        cur.execute("""
            SELECT 
                p.payment_id,
                p.payment_reference_number,
                p.payment_amount,
                p.payment_method,
                p.payment_status,
                p.payment_date,
                b.booking_id,
                b.booking_reference_number,
                b.booking_date,
                b.booking_status,
                r.room_number,
                r.room_type,
                r.room_price_per_sem,
                h.hostel_name,
                h.hostel_location,
                u.user_first_name,
                u.user_last_name,
                u.user_email,
                up.profile_student_id
            FROM payments p
            JOIN bookings b ON p.payment_reference_number = b.booking_reference_number
            JOIN rooms r ON b.booking_room_id = r.room_id
            JOIN hostels h ON r.room_hostel_id = h.hostel_id
            JOIN users u ON b.booking_user_id = u.user_id
            LEFT JOIN user_profile up ON u.user_id = up.profile_user_id
            WHERE p.payment_id = %s AND b.booking_user_id = %s
        """, (payment_id, user_id))
        
        payment = cur.fetchone()
        
        if not payment:
            return "Payment not found", 404
        
        return render_template('/student/payment_details.html',
                             user=current_user,
                             payment=payment)
        
    except Exception as e:
        print(f"Error getting payment details: {e}")
        return "Error loading payment details", 500
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@student.route('/student/payments/<int:payment_id>/receipt')
@login_required
def download_payment_receipt(payment_id):
    # This would generate and return a PDF receipt
    # Implementation depends on your PDF generation library
    pass

@student.route('/student/payments/export/pdf')
@login_required
def export_payments_pdf():
    # Generate PDF export of payment history
    pass

@student.route('/student/payments/export/csv')
@login_required
def export_payments_csv():
    # Generate CSV export of payment history
    pass

def get_student_notifications_count(cur, user_id):
    """Get count of pending notifications for student"""
    try:
        cur.execute("""
            SELECT COUNT(*) as count 
            FROM bookings 
            WHERE booking_user_id = %s 
            AND booking_status = 'Pending'
        """, (user_id,))
        result = cur.fetchone()
        return result['count'] if result else 0
    except Exception as e:
        print(f"Error getting notifications count: {e}")
        return 0



############### SUPPORT #############
@student.route('/student/support')
@login_required
def student_support():
    try:
        # Get notifications count
        notifications_count = 0
        
        return render_template('/student/support.html',
                             user=current_user,
                             notifications_count=notifications_count)
    except Exception as e:
        print(f"Error in student support: {e}")
        return render_template('/student/support.html',
                             user=current_user,
                             notifications_count=0)




######################### SETTINGS ########################
@student.route('/student/settings')
@login_required
def student_settings():
    """Student settings page"""
    conn = None
    cur = None
    try:
        conn = get_db_connection()
        cur = conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        
        # Get user profile data including account balance
        cur.execute("""
            SELECT 
                u.user_id,
                u.user_email,
                u.user_phone_number,
                u.user_first_name,
                u.user_last_name,
                u.user_gender,
                up.profile_account_balance,
                up.profile_emergency_contact,
                up.profile_student_id
            FROM users u
            LEFT JOIN user_profile up ON u.user_id = up.profile_user_id
            WHERE u.user_id = %s
        """, (current_user.id,))
        
        profile_data = cur.fetchone()
        
        # If no profile exists, create default structure
        if not profile_data:
            profile_data = {
                'profile_account_balance': 0.00,
                'profile_emergency_contact': '',
                'profile_student_id': ''
            }
        
        # Get notifications count
        notifications_count = get_student_notifications_count(cur, current_user.id)
        
        return render_template('/student/settings.html', 
                             user=current_user,
                             profile=profile_data,
                             notifications_count=notifications_count)
        
    except Exception as e:
        print(f"Error loading student settings: {e}")
        traceback.print_exc()
        # Return with default values if there's an error
        return render_template('/student/settings.html',
                             user=current_user,
                             profile={
                                 'profile_account_balance': 0.00,
                                 'profile_emergency_contact': '',
                                 'profile_student_id': ''
                             },
                             notifications_count=0)
    finally:
        if cur:
            cur.close()
        if conn:
            release_db_connection(conn)

@student.route('/student/update_profile', methods=['POST'])
@login_required
def update_student_profile():
    """Update student profile information"""
    conn = None
    cur = None
    try:
        # Get form data
        first_name = request.form.get('firstName', '').strip()
        last_name = request.form.get('lastName', '').strip()
        email = request.form.get('email', '').strip()
        phone = request.form.get('phone', '').strip()
        gender = request.form.get('gender', '').strip()
        student_id = request.form.get('studentId', '').strip()
        emergency_contact = request.form.get('emergencyContact', '').strip()
        
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
        
        # Validate gender
        if gender and gender not in ['Male', 'Female']:
            return jsonify({
                'success': False,
                'message': 'Please select a valid gender.'
            }), 400
        
        # Validate student ID
        if not student_id:
            return jsonify({
                'success': False,
                'message': 'Student ID is required.'
            }), 400
        
        # Validate emergency contact
        if not emergency_contact:
            return jsonify({
                'success': False,
                'message': 'Emergency contact is required.'
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
                user_gender = %s
            WHERE user_id = %s;
        """, (first_name, last_name, email, phone, gender, current_user.id))
        
        # Check if user profile exists
        cur.execute("SELECT profile_id FROM user_profile WHERE profile_user_id = %s", (current_user.id,))
        profile_exists = cur.fetchone()
        
        if profile_exists:
            # Update existing profile
            cur.execute("""
                UPDATE user_profile 
                SET profile_student_id = %s,
                    profile_emergency_contact = %s
                WHERE profile_user_id = %s;
            """, (student_id, emergency_contact, current_user.id))
        else:
            # Create new profile
            cur.execute("""
                INSERT INTO user_profile 
                (profile_user_id, profile_student_id, profile_emergency_contact, profile_account_balance)
                VALUES (%s, %s, %s, 0.00);
            """, (current_user.id, student_id, emergency_contact))
        
        conn.commit()
        
        return jsonify({
            'success': True,
            'message': 'Profile updated successfully!'
        })
        
    except Exception as e:
        print(f"Error updating student profile: {e}")
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


@student.route('/student/change_password', methods=['POST'])
@login_required
def change_student_password():
    """Change student password"""
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
        
        # Verify current password
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
        print(f"Error changing student password: {e}")
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
        from werkzeug.security import check_password_hash
        return check_password_hash(hashed_password, plain_password)
    except Exception as e:
        print(f"Error verifying password: {e}")
        return False

def hash_password(password):
    """Hash a password using werkzeug.security"""
    try:
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password)
    except Exception as e:
        print(f"Error hashing password: {e}")
        # Fallback
        from werkzeug.security import generate_password_hash
        return generate_password_hash(password)