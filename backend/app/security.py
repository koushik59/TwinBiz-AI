import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pymongo.database import Database

from .config import settings
from .database import get_db, oid
from .models import Business, User

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

_PBKDF2_ITERATIONS = 200_000


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _PBKDF2_ITERATIONS)
    return f"{salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        salt_hex, digest_hex = stored.split("$")
    except ValueError:
        return False
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), _PBKDF2_ITERATIONS)
    return hmac.compare_digest(digest.hex(), digest_hex)


def create_access_token(user_id: str) -> str:
    payload = {
        "sub": str(user_id),
        "exp": datetime.now(timezone.utc) + timedelta(minutes=settings.jwt_expiry_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=settings.jwt_algorithm)


def get_current_user(token: str = Depends(oauth2_scheme), db: Database = Depends(get_db)) -> User:
    credentials_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, settings.jwt_secret, algorithms=[settings.jwt_algorithm])
        user_id = payload["sub"]
    except (jwt.PyJWTError, KeyError):
        raise credentials_error
    doc = db.users.find_one({"_id": oid(user_id)})
    if doc is None:
        raise credentials_error
    return User.from_doc(doc)


def get_current_business(user: User = Depends(get_current_user), db: Database = Depends(get_db)) -> Business:
    # Newest business owned by the user (ObjectIds are time-ordered).
    doc = db.businesses.find_one({"owner_id": user.id}, sort=[("_id", -1)])
    if doc is None:
        raise HTTPException(status_code=404, detail="No business found. Create your digital twin first.")
    return Business.from_doc(doc)
