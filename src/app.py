"""High School Management System API.

A FastAPI app that allows students to view and sign up for extracurricular
activities and allows teachers to manage accounts.
"""

import hashlib
import os
import secrets
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

app = FastAPI(title="Mergington High School API",
              description="API for viewing and signing up for extracurricular activities")

# Mount the static files directory
current_dir = Path(__file__).parent
app.mount("/static", StaticFiles(directory=os.path.join(Path(__file__).parent,
          "static")), name="static")

# In-memory activity database
activities = {
    "Chess Club": {
        "description": "Learn strategies and compete in chess tournaments",
        "schedule": "Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 12,
        "participants": ["michael@mergington.edu", "daniel@mergington.edu"]
    },
    "Programming Class": {
        "description": "Learn programming fundamentals and build software projects",
        "schedule": "Tuesdays and Thursdays, 3:30 PM - 4:30 PM",
        "max_participants": 20,
        "participants": ["emma@mergington.edu", "sophia@mergington.edu"]
    },
    "Gym Class": {
        "description": "Physical education and sports activities",
        "schedule": "Mondays, Wednesdays, Fridays, 2:00 PM - 3:00 PM",
        "max_participants": 30,
        "participants": ["john@mergington.edu", "olivia@mergington.edu"]
    },
    "Soccer Team": {
        "description": "Join the school soccer team and compete in matches",
        "schedule": "Tuesdays and Thursdays, 4:00 PM - 5:30 PM",
        "max_participants": 22,
        "participants": ["liam@mergington.edu", "noah@mergington.edu"]
    },
    "Basketball Team": {
        "description": "Practice and play basketball with the school team",
        "schedule": "Wednesdays and Fridays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["ava@mergington.edu", "mia@mergington.edu"]
    },
    "Art Club": {
        "description": "Explore your creativity through painting and drawing",
        "schedule": "Thursdays, 3:30 PM - 5:00 PM",
        "max_participants": 15,
        "participants": ["amelia@mergington.edu", "harper@mergington.edu"]
    },
    "Drama Club": {
        "description": "Act, direct, and produce plays and performances",
        "schedule": "Mondays and Wednesdays, 4:00 PM - 5:30 PM",
        "max_participants": 20,
        "participants": ["ella@mergington.edu", "scarlett@mergington.edu"]
    },
    "Math Club": {
        "description": "Solve challenging problems and participate in math competitions",
        "schedule": "Tuesdays, 3:30 PM - 4:30 PM",
        "max_participants": 10,
        "participants": ["james@mergington.edu", "benjamin@mergington.edu"]
    },
    "Debate Team": {
        "description": "Develop public speaking and argumentation skills",
        "schedule": "Fridays, 4:00 PM - 5:30 PM",
        "max_participants": 12,
        "participants": ["charlotte@mergington.edu", "henry@mergington.edu"]
    }
}

# In-memory teacher account database.
SESSION_TTL_HOURS = 8
RESET_TOKEN_TTL_MINUTES = 30


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _hash_password(password: str) -> str:
    iterations = 260000
    salt_bytes = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt_bytes, iterations)
    return f"pbkdf2_sha256${iterations}${salt_bytes.hex()}${digest.hex()}"


def _verify_password(password: str, stored_hash: str) -> bool:
    if not stored_hash.startswith("pbkdf2_sha256$"):
        return False

    try:
        _, raw_iterations, raw_salt, raw_hash = stored_hash.split("$", 3)
        iterations = int(raw_iterations)
        salt_bytes = bytes.fromhex(raw_salt)
        computed = hashlib.pbkdf2_hmac(
            "sha256", password.encode("utf-8"), salt_bytes, iterations
        ).hex()
    except (TypeError, ValueError):
        return False

    return secrets.compare_digest(computed, raw_hash)


def _validate_new_password(password: str) -> None:
    if len(password) < 10:
        raise HTTPException(status_code=400, detail="Password must be at least 10 characters")


teachers = {
    "mona": {
        "username": "mona",
        "full_name": "Mona Lisa",
        "email": "mona@mergington.edu",
        "phone": "+1-555-1000",
        "avatar_url": "https://octodex.github.com/images/original.png",
        "password_hash": _hash_password("Teach3rStrong!"),
    },
    "mr-smith": {
        "username": "mr-smith",
        "full_name": "John Smith",
        "email": "john.smith@mergington.edu",
        "phone": "+1-555-2000",
        "avatar_url": "",
        "password_hash": _hash_password("AnotherStrongPass!"),
    },
}

# Token stores kept in memory for this exercise app.
sessions: dict[str, dict] = {}
password_reset_tokens: dict[str, dict] = {}


class LoginRequest(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ForgotPasswordRequest(BaseModel):
    username_or_email: str = Field(min_length=1, max_length=128)


class ResetPasswordRequest(BaseModel):
    token: str = Field(min_length=10, max_length=256)
    new_password: str = Field(min_length=10, max_length=256)


class ProfileUpdateRequest(BaseModel):
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=100)
    email: Optional[str] = Field(default=None, min_length=5, max_length=120)
    phone: Optional[str] = Field(default=None, min_length=3, max_length=30)
    avatar_url: Optional[str] = Field(default=None, max_length=300)


def _public_profile(username: str) -> dict:
    teacher = teachers[username]
    return {
        "username": teacher["username"],
        "full_name": teacher["full_name"],
        "email": teacher["email"],
        "phone": teacher["phone"],
        "avatar_url": teacher["avatar_url"],
    }


def _get_current_username(authorization: Optional[str]) -> str:
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Missing or invalid authorization header")

    token = authorization[len("Bearer "):].strip()
    session = sessions.get(token)
    if not session:
        raise HTTPException(status_code=401, detail="Invalid session token")

    if session["expires_at"] <= _utcnow():
        sessions.pop(token, None)
        raise HTTPException(status_code=401, detail="Session token expired")

    return session["username"]


@app.get("/")
def root():
    return RedirectResponse(url="/static/index.html")


@app.get("/activities")
def get_activities():
    return activities


@app.post("/auth/login")
def login(payload: LoginRequest):
    teacher = teachers.get(payload.username)
    if not teacher or not _verify_password(payload.password, teacher["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid username or password")

    token = secrets.token_urlsafe(32)
    expires_at = _utcnow() + timedelta(hours=SESSION_TTL_HOURS)
    sessions[token] = {
        "username": payload.username,
        "expires_at": expires_at,
    }

    return {
        "token": token,
        "token_type": "bearer",
        "expires_at": expires_at.isoformat(),
        "user": _public_profile(payload.username),
    }


@app.post("/auth/forgot-password")
def forgot_password(payload: ForgotPasswordRequest):
    # Keep response generic to avoid account enumeration.
    normalized = payload.username_or_email.strip().lower()
    username = None

    for candidate_username, teacher in teachers.items():
        if normalized in {candidate_username.lower(), teacher["email"].lower()}:
            username = candidate_username
            break

    response = {
        "message": "If an account exists, password reset instructions were generated."
    }

    if not username:
        return response

    reset_token = secrets.token_urlsafe(32)
    expires_at = _utcnow() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES)
    password_reset_tokens[reset_token] = {
        "username": username,
        "expires_at": expires_at,
        "used": False,
    }

    # For this exercise app, we return the token directly for demo purposes.
    response["reset_token"] = reset_token
    response["expires_at"] = expires_at.isoformat()
    return response


@app.post("/auth/reset-password")
def reset_password(payload: ResetPasswordRequest):
    _validate_new_password(payload.new_password)

    token_state = password_reset_tokens.get(payload.token)
    if not token_state:
        raise HTTPException(status_code=400, detail="Invalid reset token")
    if token_state["used"]:
        raise HTTPException(status_code=400, detail="Reset token already used")
    if token_state["expires_at"] <= _utcnow():
        raise HTTPException(status_code=400, detail="Reset token expired")

    username = token_state["username"]
    teachers[username]["password_hash"] = _hash_password(payload.new_password)
    token_state["used"] = True

    # Invalidate existing sessions for this user after password reset.
    stale_tokens = [token for token, session in sessions.items() if session["username"] == username]
    for token in stale_tokens:
        sessions.pop(token, None)

    return {"message": "Password reset successful"}


@app.get("/me/profile")
def get_profile(authorization: Optional[str] = Header(default=None)):
    username = _get_current_username(authorization)
    return _public_profile(username)


@app.put("/me/profile")
def update_profile(payload: ProfileUpdateRequest, authorization: Optional[str] = Header(default=None)):
    username = _get_current_username(authorization)
    teacher = teachers[username]

    if payload.full_name is not None:
        teacher["full_name"] = payload.full_name.strip()
    if payload.email is not None:
        teacher["email"] = payload.email.strip().lower()
    if payload.phone is not None:
        teacher["phone"] = payload.phone.strip()
    if payload.avatar_url is not None:
        teacher["avatar_url"] = payload.avatar_url.strip()

    return _public_profile(username)


@app.post("/activities/{activity_name}/signup")
def signup_for_activity(activity_name: str, email: str):
    """Sign up a student for an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is not already signed up
    if email in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is already signed up"
        )

    # Add student
    activity["participants"].append(email)
    return {"message": f"Signed up {email} for {activity_name}"}


@app.delete("/activities/{activity_name}/unregister")
def unregister_from_activity(activity_name: str, email: str):
    """Unregister a student from an activity"""
    # Validate activity exists
    if activity_name not in activities:
        raise HTTPException(status_code=404, detail="Activity not found")

    # Get the specific activity
    activity = activities[activity_name]

    # Validate student is signed up
    if email not in activity["participants"]:
        raise HTTPException(
            status_code=400,
            detail="Student is not signed up for this activity"
        )

    # Remove student
    activity["participants"].remove(email)
    return {"message": f"Unregistered {email} from {activity_name}"}
