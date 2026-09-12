"""FastAPI authentication dependencies."""

from typing import Annotated

from fastapi import Depends, Request, status
from fastapi.security import OAuth2PasswordBearer

from backend.app.auth.security import InvalidTokenError, decode_access_token
from backend.app.core.config import Settings
from backend.app.core.errors import ApplicationError
from backend.app.db.session import SessionDep
from backend.app.models.user import User
from backend.app.repositories.users import get_user_by_id

# OAuth2 describes how FastAPI obtains the Bearer token from the Authorization header of the request.
# JWT is the actual token format used in this application.
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login") 


def get_request_settings(request: Request) -> Settings:
    """Return settings loaded during application startup."""
    settings: Settings = request.app.state.settings
    return settings


SettingsDep = Annotated[Settings, Depends(get_request_settings)]


async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)], # OAuth2PasswordBearer tells FastAPI that protected endpoints expect an HTTP header in this form.
    settings: SettingsDep,
    session: SessionDep,
) -> User:
    """
    Resolve the authenticated user exclusively from a verified access token.
    - The dependency call decode_access_token() to verify the token and extract the user ID from its claims.
    - Validate user if request carries valid token and the user account is active.
    
    """
    unauthorized = ApplicationError(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code="invalid_token",
        message="Authentication credentials are invalid or expired",
    )
    try:
        claims = decode_access_token(token, settings)
        print(f"Decoded claims: {claims}")
        """
        decode_access_token extracts the following claims from the JWT token:{
            "user_id": claims.user_id,
            "exp": claims.exp,
            "iat": claims.iat
        }
        """
        
    except InvalidTokenError as exc: # claims.expired or claims.invalid
        raise unauthorized from exc
    user = await get_user_by_id(session, claims.user_id)
    if user is None or not user.is_active:
        raise unauthorized
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]
