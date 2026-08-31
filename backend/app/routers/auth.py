from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Account, RefreshToken, Guest
from app.security import hash_password, verify_password, create_access_token, generate_refresh_token, hash_token
from app.schemas import RegisterRequest, LoginRequest, RefreshRequest, TokenResponse, AccountResponse, MessageResponse, ErrorResponse
from app.dependencies import get_current_user
from app.exceptions import UnauthorizedException, ConflictException, UnprocessableException

router = APIRouter(prefix="/auth", tags=["Authentication"])

# Simple in-memory rate limiter for login
_login_attempts = {}

@router.post(
    "/register",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new guest account",
    description="Registers a self-service guest account. Unconditionally assigns role='guest'.",
    responses={
        201: {"model": AccountResponse, "description": "Account created successfully"},
        409: {"model": ErrorResponse, "description": "Email already registered"},
        422: {"model": ErrorResponse, "description": "Validation error"}
    }
)
def register(req: RegisterRequest, db: Session = Depends(get_db)):
    email_clean = req.email.lower().strip()

    # Check if account email already exists
    existing = db.query(Account).filter(Account.email == email_clean).first()
    if existing:
        raise ConflictException(message="An account with this email address is already registered.", code="EMAIL_EXISTS")

    # Link with existing guest record if present, otherwise create new guest entry
    guest = db.query(Guest).filter(Guest.email == email_clean).first()
    if not guest:
        guest = Guest(
            name=req.name.strip(),
            email=email_clean,
            phone=req.phone,
            city=req.city
        )
        db.add(guest)
        db.flush()

    new_account = Account(
        name=req.name.strip(),
        email=email_clean,
        password_hash=hash_password(req.password),
        role="guest",
        property_id=None,
        guest_id=guest.guest_id
    )
    db.add(new_account)
    db.commit()
    db.refresh(new_account)
    return new_account

@router.post(
    "/login",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Authenticate credentials and obtain JWT tokens",
    description="Validates email and password, rate limits repeated failed attempts, and returns access and refresh tokens.",
    responses={
        200: {"model": TokenResponse, "description": "Authentication successful"},
        401: {"model": ErrorResponse, "description": "Invalid email or password"},
        429: {"model": ErrorResponse, "description": "Too many failed login attempts"}
    }
)
def login(req: LoginRequest, request: Request, db: Session = Depends(get_db)):
    client_ip = request.client.host if request.client else "unknown"
    now = datetime.now(timezone.utc)

    # Rate limiting: 200 attempts threshold
    attempts = _login_attempts.get(client_ip, [])
    attempts = [t for t in attempts if (now - t).total_seconds() < 60]
    _login_attempts[client_ip] = attempts

    if len(attempts) >= 50:
        from fastapi.responses import JSONResponse
        return JSONResponse(
            status_code=429,
            content={
                "error": {
                    "code": "TOO_MANY_REQUESTS",
                    "message": "Too many login attempts. Please try again later.",
                    "details": []
                }
            }
        )

    _login_attempts[client_ip].append(now)

    email_clean = req.email.lower().strip()
    account = db.query(Account).filter(Account.email == email_clean).first()

    # Constant-time message to prevent email enumeration
    if not account or not verify_password(req.password, account.password_hash) or not account.is_active:
        raise UnauthorizedException(message="Invalid email or password", code="INVALID_CREDENTIALS")

    # Generate tokens
    token_data = {
        "sub": str(account.account_id),
        "account_id": account.account_id,
        "email": account.email,
        "role": account.role,
        "property_id": account.property_id,
        "guest_id": account.guest_id,
        "name": account.name
    }
    access_token = create_access_token(token_data)

    raw_refresh = generate_refresh_token()
    token_hash = hash_token(raw_refresh)
    refresh_record = RefreshToken(
        account_id=account.account_id,
        token_hash=token_hash,
        expires_at=now + timedelta(days=7)
    )
    db.add(refresh_record)
    db.commit()

    return TokenResponse(
        access_token=access_token,
        refresh_token=raw_refresh,
        token_type="bearer",
        expires_in=900
    )

@router.post(
    "/refresh",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Rotate refresh token and issue new access token",
    responses={
        200: {"model": TokenResponse, "description": "Tokens successfully rotated"},
        401: {"model": ErrorResponse, "description": "Invalid or reused refresh token"}
    }
)
def refresh_token(req: RefreshRequest, db: Session = Depends(get_db)):
    token_hash = hash_token(req.refresh_token)
    record = db.query(RefreshToken).filter(RefreshToken.token_hash == token_hash).first()
    now = datetime.now(timezone.utc)

    if not record:
        raise UnauthorizedException(message="Invalid refresh token", code="INVALID_TOKEN")

    if record.revoked:
        # Token reuse attack detected! Revoke all tokens for this account
        db.query(RefreshToken).filter(RefreshToken.account_id == record.account_id).update({"revoked": True})
        db.commit()
        raise UnauthorizedException(message="Refresh token was already used and revoked. Session terminated.", code="TOKEN_REVOKED")

    if record.expires_at < now:
        raise UnauthorizedException(message="Refresh token has expired", code="TOKEN_EXPIRED")

    account = db.query(Account).filter(Account.account_id == record.account_id).first()
    if not account or not account.is_active:
        raise UnauthorizedException(message="Account is inactive or not found", code="ACCOUNT_INACTIVE")

    # Rotate token
    new_raw_refresh = generate_refresh_token()
    new_token_hash = hash_token(new_raw_refresh)

    record.revoked = True
    record.replaced_by = new_token_hash

    new_record = RefreshToken(
        account_id=account.account_id,
        token_hash=new_token_hash,
        expires_at=now + timedelta(days=7)
    )
    db.add(new_record)

    token_data = {
        "sub": str(account.account_id),
        "account_id": account.account_id,
        "email": account.email,
        "role": account.role,
        "property_id": account.property_id,
        "guest_id": account.guest_id,
        "name": account.name
    }
    new_access_token = create_access_token(token_data)
    db.commit()

    return TokenResponse(
        access_token=new_access_token,
        refresh_token=new_raw_refresh,
        token_type="bearer",
        expires_in=900
    )

@router.post(
    "/logout",
    response_model=MessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Revoke refresh token on logout",
    responses={
        200: {"model": MessageResponse, "description": "Logged out successfully"},
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    }
)
def logout(req: RefreshRequest, current_user: Account = Depends(get_current_user), db: Session = Depends(get_db)):
    token_hash = hash_token(req.refresh_token)
    record = db.query(RefreshToken).filter(
        RefreshToken.token_hash == token_hash,
        RefreshToken.account_id == current_user.account_id
    ).first()
    if record:
        record.revoked = True
        db.commit()
    return MessageResponse(message="Successfully logged out.")

@router.get(
    "/me",
    response_model=AccountResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current authenticated user profile",
    responses={
        200: {"model": AccountResponse, "description": "User profile returned successfully"},
        401: {"model": ErrorResponse, "description": "Unauthorized"}
    }
)
def get_me(current_user: Account = Depends(get_current_user)):
    return current_user
