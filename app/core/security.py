import jwt
from fastapi import Security, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.core.config import settings
from datetime import datetime, timezone

security = HTTPBearer()

def validate_api_key(auth: HTTPAuthorizationCredentials = Security(security)):
    """
    ตรวจสอบ JWT Token ที่ส่งมาจาก Laravel Frontend
    """
    try:
        payload = jwt.decode(
            auth.credentials, 
            settings.JWT_SECRET, 
            algorithms=[settings.JWT_ALGORITHM]
        )
        return payload
        
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token has expired",
        )
    except jwt.InvalidTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid JWT Token: {str(e)}",
        )
