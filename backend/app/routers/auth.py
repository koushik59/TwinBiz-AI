from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, EmailStr
from pymongo.database import Database
from pymongo.errors import DuplicateKeyError

from ..database import get_db
from ..models import User, insert_model
from ..security import create_access_token, get_current_user, hash_password, verify_password

router = APIRouter(prefix="/api/auth", tags=["auth"])


class RegisterIn(BaseModel):
    full_name: str
    email: EmailStr
    password: str


class LoginIn(BaseModel):
    email: EmailStr
    password: str


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"
    has_business: bool = False


@router.post("/register", response_model=TokenOut)
def register(body: RegisterIn, db: Database = Depends(get_db)):
    if db.users.find_one({"email": body.email}):
        raise HTTPException(status_code=400, detail="Email already registered")
    if len(body.password) < 6:
        raise HTTPException(status_code=400, detail="Password must be at least 6 characters")
    user = User(email=body.email, full_name=body.full_name, password_hash=hash_password(body.password))
    try:
        insert_model(db, user)
    except DuplicateKeyError:
        raise HTTPException(status_code=400, detail="Email already registered")
    return TokenOut(access_token=create_access_token(user.id), has_business=False)


@router.post("/login", response_model=TokenOut)
def login(body: LoginIn, db: Database = Depends(get_db)):
    doc = db.users.find_one({"email": body.email})
    user = User.from_doc(doc) if doc else None
    if not user or not verify_password(body.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")
    has_business = db.businesses.find_one({"owner_id": user.id}) is not None
    return TokenOut(access_token=create_access_token(user.id), has_business=has_business)


@router.get("/me")
def me(user: User = Depends(get_current_user), db: Database = Depends(get_db)):
    business = db.businesses.find_one({"owner_id": user.id})
    return {
        "id": user.id, "email": user.email, "full_name": user.full_name, "role": user.role,
        "has_business": business is not None,
        "business_id": str(business["_id"]) if business else None,
    }
