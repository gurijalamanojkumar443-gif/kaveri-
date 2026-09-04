--Q-3.1
TRUNCATE TABLE review, payment, booking, room, guest, rate, room_type, property
RESTART IDENTITY CASCADE;

INSERT INTO property (name, city, stars)
SELECT DISTINCT
    hotel_name,
    hotel_city,
    hotel_star::SMALLINT
FROM legacy_reservations;

-- STEP 3: Populate room types
INSERT INTO room_type (type_name, max_occupancy)
VALUES
    ('Standard', 2),
    ('Deluxe', 3),
    ('Suite', 4);
-- STEP 4: Populate guests
-- One guest per email, case-insensitively

INSERT INTO guest (name, email, phone, city)
SELECT DISTINCT ON (LOWER(TRIM(guest_email)))
    TRIM(guest_name),
    LOWER(TRIM(guest_email)),
    TRIM(guest_phone),
    TRIM(guest_city)
FROM legacy_reservations
ORDER BY
    LOWER(TRIM(guest_email)),
    LENGTH(TRIM(guest_name)) DESC;

-- STEP 5: Populate rooms
-- One physical room per property + room number
INSERT INTO room (property_id,room_number,room_type_id)
SELECT DISTINCT
    p.property_id,
    TRIM(r.room_number),
    rt.room_type_id
FROM legacy_reservations l
JOIN property p
    ON p.name = l.hotel_name
   AND p.city = l.hotel_city
CROSS JOIN LATERAL
    unnest(string_to_array(l.room_numbers, ',')) AS r(room_number)
JOIN room_type rt
    ON LOWER(rt.type_name) = LOWER(TRIM(l.room_type))
ON CONFLICT (property_id, room_number) DO NOTHING;

-- STEP 6: Populate bookings
-- One booking per room
INSERT INTO booking (
    guest_id,
    room_id,
    check_in,
    check_out,
    guest_count,
    status
)
SELECT
    g.guest_id,
    r.room_id,

    CASE
        WHEN l.checkin ~ '^\d{4}-\d{2}-\d{2}$'
            THEN TO_DATE(l.checkin, 'YYYY-MM-DD')

        WHEN l.checkin ~ '^\d{2}/\d{2}/\d{4}$'
            THEN TO_DATE(l.checkin, 'DD/MM/YYYY')

        ELSE
            TO_DATE(l.checkin, 'FMMonth DD, YYYY')
    END,

    CASE
        WHEN l.checkout ~ '^\d{4}-\d{2}-\d{2}$'
            THEN TO_DATE(l.checkout, 'YYYY-MM-DD')

        WHEN l.checkout ~ '^\d{2}/\d{2}/\d{4}$'
            THEN TO_DATE(l.checkout, 'DD/MM/YYYY')

        ELSE
            TO_DATE(l.checkout, 'FMMonth DD, YYYY')
    END,

    CEIL(
        l.guests_count::NUMERIC
        /
        array_length(string_to_array(l.room_numbers, ','), 1)
    )::INT,

    CASE LOWER(TRIM(l.status))
        WHEN 'confirmed' THEN 'confirmed'
        WHEN 'conf' THEN 'confirmed'
        WHEN 'cancelled' THEN 'cancelled'
        WHEN 'no show' THEN 'no_show'
        ELSE LOWER(TRIM(l.status))
    END

FROM legacy_reservations l
JOIN guest g
    ON LOWER(TRIM(g.email)) = LOWER(TRIM(l.guest_email))
JOIN property p
    ON p.name = l.hotel_name
   AND p.city = l.hotel_city
CROSS JOIN LATERAL
    unnest(string_to_array(l.room_numbers, ',')) AS room_list(room_number)
JOIN room r
    ON r.property_id = p.property_id
   AND r.room_number = TRIM(room_list.room_number);
-- STEP 7: Populate payments
INSERT INTO payment (
    booking_id,
    amount,
    method,
    payment_date
)
SELECT
    b.booking_id,

    (
        REPLACE(l.total_paid, ',', '')::NUMERIC
        /
        array_length(string_to_array(l.room_numbers, ','), 1)
    )::NUMERIC(10,2),

    CASE LOWER(TRIM(l.payment_method))
        WHEN 'card' THEN 'card'
        WHEN 'upi' THEN 'UPI'
        WHEN 'bank transfer' THEN 'bank transfer'
        WHEN 'cash' THEN 'cash'
        ELSE LOWER(TRIM(l.payment_method))
    END,

    b.check_in

FROM legacy_reservations l
JOIN guest g
    ON LOWER(TRIM(g.email)) = LOWER(TRIM(l.guest_email))
JOIN property p
    ON p.name = l.hotel_name
   AND p.city = l.hotel_city
CROSS JOIN LATERAL
    unnest(string_to_array(l.room_numbers, ',')) AS room_list(room_number)
JOIN room r
    ON r.property_id = p.property_id
   AND r.room_number = TRIM(room_list.room_number)
JOIN booking b
    ON b.guest_id = g.guest_id
   AND b.room_id = r.room_id
   AND b.check_in = CASE
        WHEN l.checkin ~ '^\d{4}-\d{2}-\d{2}$'
            THEN TO_DATE(l.checkin, 'YYYY-MM-DD')
        WHEN l.checkin ~ '^\d{2}/\d{2}/\d{4}$'
            THEN TO_DATE(l.checkin, 'DD/MM/YYYY')
        ELSE
            TO_DATE(l.checkin, 'FMMonth DD, YYYY')
    END;
-- STEP 8: Populate rate plans
INSERT INTO rate (
    property_id,
    room_type_id,
    start_date,
    end_date,
    nightly_rate
)
SELECT
    p.property_id,
    rt.room_type_id,
    MIN(
        CASE
            WHEN l.checkin ~ '^\d{4}-\d{2}-\d{2}$'
                THEN TO_DATE(l.checkin, 'YYYY-MM-DD')
            WHEN l.checkin ~ '^\d{2}/\d{2}/\d{4}$'
                THEN TO_DATE(l.checkin, 'DD/MM/YYYY')
            ELSE
                TO_DATE(l.checkin, 'FMMonth DD, YYYY')
        END
    ),
    MAX(
        CASE
            WHEN l.checkout ~ '^\d{4}-\d{2}-\d{2}$'
                THEN TO_DATE(l.checkout, 'YYYY-MM-DD')
            WHEN l.checkout ~ '^\d{2}/\d{2}/\d{4}$'
                THEN TO_DATE(l.checkout, 'DD/MM/YYYY')
            ELSE
                TO_DATE(l.checkout, 'FMMonth DD, YYYY')
        END
    ),
    MIN(REPLACE(l.nightly_rate, ',', '')::NUMERIC(10,2))
FROM legacy_reservations l
JOIN property p
    ON p.name = l.hotel_name
   AND p.city = l.hotel_city
JOIN room_type rt
    ON LOWER(rt.type_name) = LOWER(TRIM(l.room_type))
GROUP BY
    p.property_id,
    rt.room_type_id;
COMMIT;
--Q-3.2
INSERT INTO guest (name, email, phone, city)
SELECT DISTINCT ON (LOWER(TRIM(guest_email)))
       TRIM(guest_name),
       LOWER(TRIM(guest_email)),
       guest_phone,
       guest_city
FROM legacy_reservations
ORDER BY LOWER(TRIM(guest_email)),
         LENGTH(TRIM(guest_name)) DESC
ON CONFLICT (email) DO NOTHING;

SELECT COUNT(*) AS legacy_rows
FROM legacy_reservations;

SELECT COUNT(*) AS unique_guests
FROM guest;

--Q-3.3
UPDATE guest
SET phone =
REGEXP_REPLACE(phone,'[^0-9+]','','g');

--3.4
SELECT
CASE
    WHEN checkin ~ '^\d{4}-\d{2}-\d{2}$'
        THEN TO_DATE(checkin,'YYYY-MM-DD')
    WHEN checkin ~ '^\d{2}/\d{2}/\d{4}$'
        THEN TO_DATE(checkin,'DD/MM/YYYY')
    ELSE
        TO_DATE(checkin,'FMMonth DD, YYYY')
END AS parsed_checkin
FROM legacy_reservations;

--3.5
SELECT row_id,
unnest(string_to_array(room_numbers, ',')) AS room_number
FROM legacy_reservations;

--3.6
SELECT DISTINCT
    status,
    CASE
        WHEN LOWER(TRIM(status)) IN ('confirmed', 'conf')
            THEN 'confirmed'
        WHEN LOWER(TRIM(status)) = 'cancelled'
            THEN 'cancelled'
        WHEN LOWER(TRIM(status)) = 'no show'
            THEN 'no_show'
    END AS clean_status,

    payment_method,
    CASE
        WHEN LOWER(TRIM(payment_method)) = 'card'
            THEN 'card'
        WHEN LOWER(TRIM(payment_method)) = 'upi'
            THEN 'upi'
        WHEN LOWER(TRIM(payment_method)) = 'bank transfer'
            THEN 'bank_transfer'
    END AS clean_payment_method

FROM legacy_reservations;

--3.7
SELECT nightly_rate,REPLACE(REPLACE
(nightly_rate, '₹', ''),',', '')::numeric AS rate
FROM legacy_reservations;

--3.8
SELECT(SELECT SUM(cardinality(string_to_array(room_numbers, ',')))
     FROM legacy_reservations) AS legacy_booking_count,(SELECT COUNT(*)
     FROM booking) AS booking_count,((SELECT SUM(cardinality(string_to_array(room_numbers, ',')))
     FROM legacy_reservations)-(SELECT COUNT(*)FROM booking)) AS discrepancy;

SELECT
    COUNT(*) AS legacy_count,
    (SELECT COUNT(*) FROM booking) AS booking_count,
    COUNT(*) - (SELECT COUNT(*) FROM booking) AS difference
FROM legacy_reservations; 