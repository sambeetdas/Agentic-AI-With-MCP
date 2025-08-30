# For JWT authentication
from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from jose import JWTError, jwt
from datetime import datetime, timedelta
from passlib.context import CryptContext
from typing import Any # Added for type hinting

# --- Configuration for JWT ---
SECRET_KEY = "123456"  # **IMPORTANT**: Change this to a strong, random key in production!
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Password hashing context
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

# OAuth2PasswordBearer for extracting token from header
# This tells FastAPI where to find the token.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/tool-repository/login_for_access_token") 
# IMPORTANT: Adjust tokenUrl if your login tool's path is different

# --- User Management (Example - in a real app, this would be a database) ---
fake_users_db = {
    "testuser": {
        "username": "testuser",
        "hashed_password": pwd_context.hash("testpassword"),
        "full_name": "Test User",
        "email": "test@example.com",
        "disabled": False,
    }
}

def require_auth_tool(func):
    async def wrapper(*args, token: str = None, **kwargs):
        if not token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Token required"
            )
        auth_service = AuthService()
        user = auth_service.get_user(token)
        return await func(*args, current_user=user, **kwargs)
    return wrapper

class AuthService:
    def verify_password(self, plain_password, hashed_password):
        return pwd_context.verify(plain_password, hashed_password)

    def get_user(self, username: str):
        if username in fake_users_db:
            user_dict = fake_users_db[username]
            return user_dict
        return None

    # --- JWT Token Functions ---
    def create_access_token(self, data: dict, expires_delta: timedelta | None = None):
        to_encode = data.copy()
        if expires_delta:
            expire = datetime.utcnow() + expires_delta
        else:
            expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
        to_encode.update({"exp": expire})
        encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
        return encoded_jwt

    def decode_access_token(self, token: str):
        try:
            payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
            username: str = payload.get("sub")
            if username is None:
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="Could not validate credentials",
                    headers={"WWW-Authenticate": "Bearer"},
                )
            return payload
        except JWTError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )

    # --- Dependency to get the current authenticated user ---
    # This now takes the token directly from oauth2_scheme (which handles header extraction)
    async def get_current_user(self, token: str = Depends(oauth2_scheme)) -> dict:
        payload = self.decode_access_token(token)
        username = payload.get("sub")
        user = self.get_user(username)
        if user is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found", # More specific error
                headers={"WWW-Authenticate": "Bearer"},
            )
        return user