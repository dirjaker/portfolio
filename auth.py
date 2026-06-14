from fastapi import Request, HTTPException
from fastapi.responses import RedirectResponse
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired
from config import SECRET_KEY

serializer = URLSafeTimedSerializer(SECRET_KEY)

def create_session_token(username: str) -> str:
    return serializer.dumps(username)

def verify_session_token(token: str, max_age: int = 86400) -> str | None:
    try:
        return serializer.loads(token, max_age=max_age)
    except (BadSignature, SignatureExpired):
        return None

def get_current_user(request: Request) -> str | None:
    token = request.cookies.get("session")
    if not token:
        return None
    return verify_session_token(token)

def require_admin(request: Request) -> str:
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=303, headers={"Location": "/admin/login"})
    return user
