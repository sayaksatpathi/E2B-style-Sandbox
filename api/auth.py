import os
import logging
from datetime import datetime, timedelta
from typing import Optional

from fastapi import HTTPException, Security, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials, APIKeyHeader
from jose import jwt, JWTError

logger = logging.getLogger(__name__)

SECRET_KEY = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-production")
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "60"))

# Static API keys for development (use a DB or vault in production)
VALID_API_KEYS = set(os.getenv("API_KEYS", "dev-api-key-1,dev-api-key-2").split(","))

bearer_scheme = HTTPBearer(auto_error=False)
api_key_header = APIKeyHeader(name="X-API-Key", auto_error=False)


def create_access_token(user_id: str, expires_delta: Optional[timedelta] = None) -> str:
    data = {"sub": user_id, "iat": datetime.utcnow()}
    expire = datetime.utcnow() + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    data["exp"] = expire
    return jwt.encode(data, SECRET_KEY, algorithm=ALGORITHM)


def decode_token(token: str) -> dict:
    return jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])


async def get_current_user(
    bearer: Optional[HTTPAuthorizationCredentials] = Security(bearer_scheme),
    api_key: Optional[str] = Security(api_key_header),
) -> str:
    # Try Bearer JWT first
    if bearer and bearer.credentials:
        try:
            payload = decode_token(bearer.credentials)
            user_id = payload.get("sub")
            if user_id:
                return user_id
        except JWTError as e:
            logger.debug(f"JWT decode error: {e}")

    # Try API Key
    if api_key and api_key in VALID_API_KEYS:
        # Use the key itself as a user identifier (prefix for namespacing)
        return f"apikey:{api_key[:8]}"

    raise HTTPException(status_code=401, detail="Invalid or missing authentication credentials.")
