from datetime import date
from decimal import Decimal
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.schemas import OccupancyReportResponse, RevenueReportResponse

def get_occupancy_metrics(
    db: Session,
    start_date: date,
    end_date: date,
    property_id: Optional[int] = None
) -> List[OccupancyReportResponse]:
    """
    Computes property occupancy metrics in PostgreSQL.
    """
    query = """
    WITH property_rooms AS (
        SELECT p.property_id, p.name AS property_name, COUNT(r.room_id) AS total_rooms
        FROM property p
        LEFT JOIN room r ON r.property_id = p.property_id
        WHERE (:prop_id IS NULL OR p.property_id = :prop_id)
        GROUP BY p.property_id, p.name
    ),
    occupied_nights AS (
        SELECT
            r.property_id,
            COUNT(*) AS occupied_room_nights
        FROM booking b
        JOIN room r ON r.room_id = b.room_id
        CROSS JOIN LATERAL generate_series(b.check_in, b.check_out - INTERVAL '1 day', INTERVAL '1 day') AS stay_date
        WHERE b.status IN ('confirmed', 'checked_in', 'checked_out')
          AND stay_date >= :start_date
          AND stay_date < :end_date
          AND (:prop_id IS NULL OR r.property_id = :prop_id)
        GROUP BY r.property_id
    )
    SELECT
        pr.property_id,
        pr.property_name,
        pr.total_rooms,
        COALESCE(oc.occupied_room_nights, 0) AS occupied_room_nights,
        (pr.total_rooms * (:num_days)) AS available_room_nights,
        CASE
            WHEN (pr.total_rooms * (:num_days)) > 0
            THEN ROUND((COALESCE(oc.occupied_room_nights, 0)::NUMERIC / (pr.total_rooms * (:num_days)) * 100.0), 2)
            ELSE 0.00
        END AS occupancy_percentage
    FROM property_rooms pr
    LEFT JOIN occupied_nights oc ON oc.property_id = pr.property_id
    ORDER BY pr.property_id;
    """

    num_days = max(1, (end_date - start_date).days)
    result = db.execute(
        text(query),
        {
            "prop_id": property_id,
            "start_date": start_date,
            "end_date": end_date,
            "num_days": num_days
        }
    ).fetchall()

    reports = []
    for r in result:
        reports.append(OccupancyReportResponse(
            property_id=r[0],
            property_name=r[1],
            total_rooms=int(r[2]),
            occupied_room_nights=int(r[3]),
            available_room_nights=int(r[4]),
            occupancy_percentage=float(r[5])
        ))
    return reports

def get_revenue_metrics(
    db: Session,
    start_date: date,
    end_date: date,
    property_id: Optional[int] = None
) -> List[RevenueReportResponse]:
    """
    Computes total revenue, Average Daily Rate (ADR), and Revenue Per Available Room (RevPAR) in SQL.
    """
    query = """
    WITH property_rooms AS (
        SELECT p.property_id, p.name AS property_name, COUNT(r.room_id) AS total_rooms
        FROM property p
        LEFT JOIN room r ON r.property_id = p.property_id
        WHERE (:prop_id IS NULL OR p.property_id = :prop_id)
        GROUP BY p.property_id, p.name
    ),
    revenue_calc AS (
        SELECT
            r.property_id,
            SUM(pm.amount) AS total_revenue,
            COUNT(DISTINCT b.booking_id) AS total_bookings,
            COUNT(*) AS occupied_nights
        FROM payment pm
        JOIN booking b ON b.booking_id = pm.booking_id
        JOIN room r ON r.room_id = b.room_id
        CROSS JOIN LATERAL generate_series(b.check_in, b.check_out - INTERVAL '1 day', INTERVAL '1 day') AS stay_date
        WHERE b.status IN ('confirmed', 'checked_in', 'checked_out')
          AND stay_date >= :start_date
          AND stay_date < :end_date
          AND (:prop_id IS NULL OR r.property_id = :prop_id)
        GROUP BY r.property_id
    )
    SELECT
        pr.property_id,
        pr.property_name,
        COALESCE(rc.total_revenue, 0.00) AS total_revenue,
        CASE
            WHEN COALESCE(rc.occupied_nights, 0) > 0
            THEN ROUND((COALESCE(rc.total_revenue, 0.00) / rc.occupied_nights)::NUMERIC, 2)
            ELSE 0.00
        END AS adr,
        CASE
            WHEN (pr.total_rooms * (:num_days)) > 0
            THEN ROUND((COALESCE(rc.total_revenue, 0.00) / (pr.total_rooms * (:num_days)))::NUMERIC, 2)
            ELSE 0.00
        END AS revpar
    FROM property_rooms pr
    LEFT JOIN revenue_calc rc ON rc.property_id = pr.property_id
    ORDER BY pr.property_id;
    """

    num_days = max(1, (end_date - start_date).days)
    result = db.execute(
        text(query),
        {
            "prop_id": property_id,
            "start_date": start_date,
            "end_date": end_date,
            "num_days": num_days
        }
    ).fetchall()

    reports = []
    for r in result:
        reports.append(RevenueReportResponse(
            property_id=r[0],
            property_name=r[1],
            total_revenue=float(r[2]),
            adr=float(r[3]),
            revpar=float(r[4])
        ))
    return reports
