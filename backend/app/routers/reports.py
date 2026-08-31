from datetime import date
from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.schemas import OccupancyReportResponse, RevenueReportResponse, ErrorResponse
from app.dependencies import require_manager
from app.services.report_service import get_occupancy_metrics, get_revenue_metrics
from app.models import Account
from app.exceptions import UnprocessableException

router = APIRouter(prefix="/reports", tags=["Reports"])

@router.get(
    "/occupancy",
    response_model=List[OccupancyReportResponse],
    status_code=status.HTTP_200_OK,
    summary="Occupancy report by property and date range",
    description="Managers see only their property; owner sees all properties or filters by property_id.",
    responses={
        200: {"model": List[OccupancyReportResponse], "description": "Occupancy metrics returned"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden - Staff cannot access reports"}
    }
)
def occupancy_report(
    start_date: date = Query(..., description="Report start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Report end date (YYYY-MM-DD)"),
    property_id: Optional[int] = Query(None, description="Filter by property (owner only)"),
    current_user: Account = Depends(require_manager),
    db: Session = Depends(get_db)
):
    if end_date <= start_date:
        raise UnprocessableException(message="end_date must be after start_date.")

    # Property scope enforcement
    effective_property_id = property_id
    if current_user.role == "manager":
        effective_property_id = current_user.property_id

    return get_occupancy_metrics(db, start_date, end_date, effective_property_id)


@router.get(
    "/revenue",
    response_model=List[RevenueReportResponse],
    status_code=status.HTTP_200_OK,
    summary="Revenue report: ADR and RevPAR by property",
    description="Computes total revenue, Average Daily Rate, and Revenue Per Available Room for a date range.",
    responses={
        200: {"model": List[RevenueReportResponse], "description": "Revenue metrics returned"},
        401: {"model": ErrorResponse, "description": "Unauthorized"},
        403: {"model": ErrorResponse, "description": "Forbidden - Staff cannot access reports"}
    }
)
def revenue_report(
    start_date: date = Query(..., description="Report start date (YYYY-MM-DD)"),
    end_date: date = Query(..., description="Report end date (YYYY-MM-DD)"),
    property_id: Optional[int] = Query(None, description="Filter by property (owner only)"),
    current_user: Account = Depends(require_manager),
    db: Session = Depends(get_db)
):
    if end_date <= start_date:
        raise UnprocessableException(message="end_date must be after start_date.")

    effective_property_id = property_id
    if current_user.role == "manager":
        effective_property_id = current_user.property_id

    return get_revenue_metrics(db, start_date, end_date, effective_property_id)
