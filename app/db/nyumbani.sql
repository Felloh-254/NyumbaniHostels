CREATE TABLE users (
    user_id SERIAL PRIMARY KEY,
    user_email VARCHAR(50) UNIQUE NOT NULL,
    user_phone_number VARCHAR(20),
    user_first_name VARCHAR(50) NOT NULL,
    user_last_name VARCHAR(50) NOT NULL,
    user_gender VARCHAR(20) CHECK(user_gender IN ('Male', 'Female')) NOT NULL,
    user_password_hash TEXT
);

CREATE TABLE user_profile (
    profile_id SERIAL PRIMARY KEY,
    profile_user_id INTEGER UNIQUE REFERENCES users(user_id) ON DELETE CASCADE,
    profile_account_balance NUMERIC(10,2) DEFAULT 0.00 NOT NULL,
    profile_emergency_contact VARCHAR(20),
    profile_student_id VARCHAR(20) NOT NULL,
);

CREATE TABLE roles (
    role_id SERIAL PRIMARY KEY,
    role_name VARCHAR(50) CHECK(role_name IN ('student', 'admin')) UNIQUE NOT NULL
);

CREATE TABLE user_roles (
    user_role_user_id INTEGER REFERENCES users(user_id) ON DELETE CASCADE,
    user_role_role_id INTEGER REFERENCES roles(role_id) ON DELETE CASCADE,
    PRIMARY KEY (user_role_user_id, user_role_role_id)
);

CREATE TABLE hostels (
    hostel_id SERIAL PRIMARY KEY,
    hostel_name VARCHAR(20) NOT NULL,
    hostel_location VARCHAR(20),
    hostel_total_rooms INTEGER NOT NULL,
    hostel_description TEXT,
    hostel_image TEXT
);

CREATE TABLE rooms (
    room_id SERIAL PRIMARY KEY,
    room_hostel_id INTEGER NOT NULL REFERENCES hostels(hostel_id) ON DELETE CASCADE,
    room_number VARCHAR(10) UNIQUE NOT NULL,
    room_type VARCHAR(20) DEFAULT 'Single' CHECK(room_type IN ('Single', 'Double', 'Shared')) NOT NULL,
    room_capacity INTEGER NOT NULL,
    room_price_per_sem NUMERIC(10,2) NOT NULL,
    UNIQUE(room_hostel_id, room_number)
);

CREATE TABLE room_images (
    image_id SERIAL PRIMARY KEY,
    image_room_id INTEGER REFERENCES rooms(room_id) ON DELETE CASCADE,
    image_url TEXT
);

CREATE TABLE bookings (
    booking_id SERIAL PRIMARY KEY,
    booking_reference_number VARCHAR(50) UNIQUE NOT NULL,
    booking_user_id INTEGER NOT NULL REFERENCES users(user_id) ON DELETE CASCADE,
    booking_room_id INTEGER NOT NULL REFERENCES rooms(room_id) ON DELETE CASCADE,
    booking_date DATE DEFAULT CURRENT_DATE,
    booking_status VARCHAR(20) DEFAULT 'Pending' CHECK(booking_status IN ('Pending', 'Confirmed', 'Cancelled')) NOT NULL,
    UNIQUE(booking_user_id, booking_room_id)
);

CREATE TABLE payments (
    payment_id SERIAL PRIMARY KEY,
    payment_reference_number VARCHAR(50) UNIQUE NOT NULL,
    payment_amount NUMERIC(10,2) NOT NULL,
    payment_method VARCHAR(20) NOT NULL CHECK(payment_method IN ('Mpesa', 'Cash')),
    payment_date DATE DEFAULT CURRENT_DATE,
    payment_status VARCHAR DEFAULT 'Pending' CHECK(payment_status IN ('Success', 'Failed', 'Pending')),
    payment_receipt TEXT
);

CREATE TABLE allocations (
    allocation_id SERIAL PRIMARY KEY,
    allocation_booking_id INTEGER UNIQUE NOT NULL REFERENCES bookings(booking_id) ON DELETE CASCADE,
    allocation_payment_id INTEGER REFERENCES payments(payment_id),
    allocation_date DATE DEFAULT CURRENT_DATE,
    allocation_vaccate_date DATE NOT NULL
);



INSERT INTO room_images (image_room_id, image_url) VALUES
(1, 'https://images.unsplash.com/photo-1586023492125-27b2c045efd7?w=500&h=300&fit=crop'),
(1, 'https://images.unsplash.com/photo-1564078516393-cf04bd966897?w=500&h=300&fit=crop'),
(2, 'https://images.unsplash.com/photo-1584622650111-993a426fbf0a?w=500&h=300&fit=crop'),
(2, 'https://images.unsplash.com/photo-1566665797739-1674de7a421a?w=500&h=300&fit=crop'),
(3, 'https://images.unsplash.com/photo-1555854877-bab0e564b8d5?w=500&h=300&fit=crop'),
(3, 'https://images.unsplash.com/photo-1595428774223-ef52624120d2?w=500&h=300&fit=crop'),
(4, 'https://images.unsplash.com/photo-1631049307264-da0ec9d70304?w=500&h=300&fit=crop'),
(4, 'https://images.unsplash.com/photo-1599809275671-b5942cabc7a2?w=500&h=300&fit=crop'),
(5, 'https://images.unsplash.com/photo-1588046130717-0eb1c9a169ba?w=500&h=300&fit=crop'),
(5, 'https://images.unsplash.com/photo-1595526114035-0d45ed16cfbf?w=500&h=300&fit=crop');
(6, 'https://images.unsplash.com/photo-1554995207-c18c203602cb?w=500&h=300&fit=crop'),
(6, 'https://images.unsplash.com/photo-1502672260266-1c1ef2d93688?w=500&h=300&fit=crop');