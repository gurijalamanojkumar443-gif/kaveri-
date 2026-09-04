--1. Property
CREATE TABLE property (
    property_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    city VARCHAR(50) NOT NULL,
    stars SMALLINT CHECK (stars BETWEEN 1 AND 5)
);
--2. Room Type
CREATE TABLE room_type (
    room_type_id SERIAL PRIMARY KEY,
    type_name VARCHAR(20) UNIQUE NOT NULL,
    max_occupancy SMALLINT NOT NULL CHECK (max_occupancy > 0)
);
--3. Guest
CREATE TABLE guest (
    guest_id SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    phone VARCHAR(20),
    city VARCHAR(50)
);
--4. Room
CREATE TABLE room (
    room_id SERIAL PRIMARY KEY,
    property_id INT NOT NULL REFERENCES property(property_id),
    room_number VARCHAR(10) NOT NULL,
    room_type_id INT NOT NULL REFERENCES room_type(room_type_id),
    UNIQUE(property_id, room_number)
);
--5. Booking

--Now this will work because guest and room already exist.

CREATE TABLE booking (
    booking_id SERIAL PRIMARY KEY,
    guest_id INT NOT NULL REFERENCES guest(guest_id),
    room_id INT NOT NULL REFERENCES room(room_id),
    check_in DATE NOT NULL,
    check_out DATE NOT NULL,
    guest_count INT NOT NULL CHECK (guest_count > 0),
    status VARCHAR(20) NOT NULL
);
--6. Payment
CREATE TABLE payment (
    payment_id SERIAL PRIMARY KEY,
    booking_id INT NOT NULL REFERENCES booking(booking_id),
    amount NUMERIC(10,2) NOT NULL,
    method VARCHAR(20) NOT NULL,
    payment_date DATE NOT NULL
);
--7. Review
CREATE TABLE review (
    review_id SERIAL PRIMARY KEY,
    booking_id INT UNIQUE NOT NULL REFERENCES booking(booking_id),
    rating INT CHECK (rating BETWEEN 1 AND 5),
    comment TEXT,
    review_date DATE
);
--8. Rate
CREATE TABLE rate (
    rate_id SERIAL PRIMARY KEY,
    property_id INT NOT NULL REFERENCES property(property_id),
    room_type_id INT NOT NULL REFERENCES room_type(room_type_id),
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    nightly_rate NUMERIC(10,2) NOT NULL
);