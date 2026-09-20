from jose import jwt, JWTError, ExpiredSignatureError

from fastapi import HTTPException, status

from datetime import datetime, timedelta

import os
import uuid
import hashlib


# =========================================================
# JWT CONFIG
# =========================================================

SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError("SECRET_KEY is not configured")

ALGORITHM = "HS256"

# Access token short-lived
ACCESS_TOKEN_EXPIRE_MINUTES = 15

# Refresh token long-lived
REFRESH_TOKEN_EXPIRE_DAYS = 365


# =========================================================
# HASH REFRESH TOKEN
# =========================================================

def hash_refresh_token(token: str) -> str:
    """
    Store only a SHA-256 hash of the refresh token in DB.
    """

    return hashlib.sha256(
        token.encode("utf-8")
    ).hexdigest()


# =========================================================
# CREATE ACCESS TOKEN
# =========================================================

def create_access_token(data: dict):

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        minutes=ACCESS_TOKEN_EXPIRE_MINUTES
    )

    to_encode.update({
        "exp": expire,
        "type": "access",
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# =========================================================
# CREATE REFRESH TOKEN
# =========================================================

def create_refresh_token(data: dict):

    to_encode = data.copy()

    expire = datetime.utcnow() + timedelta(
        days=REFRESH_TOKEN_EXPIRE_DAYS
    )

    to_encode.update({
        "exp": expire,
        "type": "refresh",
        "jti": str(uuid.uuid4()),
    })

    return jwt.encode(
        to_encode,
        SECRET_KEY,
        algorithm=ALGORITHM,
    )


# =========================================================
# VERIFY ACCESS TOKEN
# =========================================================

def verify_token(token: str):

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        # Must be access token
        if payload.get("type") != "access":

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token type",
            )

        # User ID required
        if not payload.get("sub"):

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token payload",
            )

        return payload

    except ExpiredSignatureError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token expired",
        )

    except JWTError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token",
        )


# =========================================================
# VERIFY REFRESH TOKEN
# =========================================================

def verify_refresh_token(token: str):

    try:

        payload = jwt.decode(
            token,
            SECRET_KEY,
            algorithms=[ALGORITHM],
        )

        # Must be refresh token
        if payload.get("type") != "refresh":

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        # User ID required
        if not payload.get("sub"):

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token payload",
            )

        # JTI required
        if not payload.get("jti"):

            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token",
            )

        return payload

    except ExpiredSignatureError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token expired",
        )

    except JWTError:

        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token",
        )