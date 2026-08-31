from typing import Optional, List
from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from app.database import get_db
from app.models import Account, Booking
from app.security import decode_access_token
from app.exceptions import UnauthorizedException, ForbiddenException, NotFoundException

security_scheme = HTTPBearer(auto_error=False)

def get_current_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Account:
    """Dependency to authenticate and return the current active user account."""
    if not auth or not auth.credentials:
        raise UnauthorizedException(message="Missing authentication token")
    
    token = auth.credentials
    try:
        payload = decode_access_token(token)
    except Exception as e:
        raise UnauthorizedException(message=f"Invalid authentication token: {str(e)}")
    
    account_id = payload.get("account_id")
    if not account_id:
        raise UnauthorizedException(message="Invalid token payload: missing account_id")
    
    account = db.query(Account).filter(Account.account_id == account_id).first()
    if not account:
        raise UnauthorizedException(message="Account not found")
    
    if not account.is_active:
        raise UnauthorizedException(message="Account is deactivated")
    
    return account

def get_optional_user(
    auth: Optional[HTTPAuthorizationCredentials] = Depends(security_scheme),
    db: Session = Depends(get_db)
) -> Optional[Account]:
    """Dependency for optional authentication."""
    if not auth or not auth.credentials:
        return None
    try:
        payload = decode_access_token(auth.credentials)
        account_id = payload.get("account_id")
        if account_id:
            return db.query(Account).filter(Account.account_id == account_id, Account.is_active == True).first()
    except Exception:
        pass
    return None

def require_role(allowed_roles: List[str]):
    """Dependency factory for role-based authorization."""
    def role_checker(current_user: Account = Depends(get_current_user)) -> Account:
        if current_user.role not in allowed_roles:
            raise ForbiddenException(
                message=f"Action requires one of the following roles: {', '.join(allowed_roles)}"
            )
        return current_user
    return role_checker

# Reusable role guards
require_guest = require_role(["guest", "staff", "manager", "owner"])
require_staff = require_role(["staff", "manager", "owner"])
require_manager = require_role(["manager", "owner"])
require_owner = require_role(["owner"])

def enforce_property_scope(property_id: Optional[int], current_user: Account) -> Optional[int]:
    """
    Enforces property scope.
    - Owner can access any property or query across all properties (property_id=None).
    - Manager and Staff are strictly restricted to their assigned property_id.
    - If a Manager requests a different property_id, raises 403 Forbidden.
    """
    if current_user.role == "owner":
        return property_id
    
    if current_user.role in ["staff", "manager"]:
        if property_id is not None and property_id != current_user.property_id:
            raise ForbiddenException(
                message=f"Access denied: you only have permission for property {current_user.property_id}."
            )
        return current_user.property_id
    
    return property_id
