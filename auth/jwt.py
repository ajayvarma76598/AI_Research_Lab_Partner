import os
import logging
from typing import Optional
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session

from db.models import get_session, User

logger = logging.getLogger(__name__)

security = HTTPBearer()

# We use JWKS for Auth0 RSA token validation.
# A more robust production implementation would use PyJWKClient.
# Since we might not have a real Auth0 domain yet, we'll provide a 
# graceful fallback for local development if auth is not configured.

def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security)):
    """
    Validates the Bearer token.
    If Auth0 is not configured in .env, this gracefully bypasses auth for local dev testing.
    """
    token = credentials.credentials
    auth0_domain = os.getenv("AUTH0_DOMAIN")
    auth0_audience = os.getenv("AUTH0_AUDIENCE")
    
    if not auth0_domain or not auth0_audience:
        # Development fallback bypass
        logger.warning("AUTH0_DOMAIN not set! Bypassing JWT validation for local development.")
        return {"sub": "dev_user_123", "email": "dev@example.com"}

    try:
        # In a real setup, fetch JWKS from f"https://{auth0_domain}/.well-known/jwks.json"
        # and use PyJWKClient. For brevity in this template, we assume standard decode.
        jwks_client = jwt.PyJWKClient(f"https://{auth0_domain}/.well-known/jwks.json")
        signing_key = jwks_client.get_signing_key_from_jwt(token)
        
        payload = jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=auth0_audience,
            issuer=f"https://{auth0_domain}/"
        )
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token has expired")
    except Exception as e:
        logger.error(f"JWT Validation failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid token")

def get_current_user(payload: dict = Depends(verify_token)) -> User:
    """
    Dependency that returns the current logged-in user.
    Creates a new user record in the DB if it's their first time logging in.
    """
    user_id = payload.get("sub")
    email = payload.get("email") # Note: Requires Auth0 to include email in token
    name = payload.get("name", "User")
    
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid token payload")
        
    session = get_session()
    try:
        user = session.query(User).filter(User.user_id == user_id).first()
        if not user:
            # First time login - create user
            user = User(user_id=user_id, email=email, name=name)
            session.add(user)
            session.commit()
            session.refresh(user)
        return user
    finally:
        session.close()
