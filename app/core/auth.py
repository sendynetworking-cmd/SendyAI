import logging
import requests as py_requests
from fastapi import Header, HTTPException
from google.oauth2 import id_token
from google.auth.transport import requests
from .config import settings

logger = logging.getLogger(__name__)

async def get_user_id(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing auth token")
    
    token = authorization.replace("Bearer ", "")
    
    # Try Access Token first
    try:
        userinfo_res = py_requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token}"}
        )
        if userinfo_res.ok:
            user_data = userinfo_res.json()
            return user_data['sub']
    except Exception as e:
        logger.error(f"Access token check logic failed: {e}")

    # Fallback/Try ID Token
    try:
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            settings.GOOGLE_CLIENT_ID
        )
        return idinfo['sub']
    except Exception as e:
        logger.error(f"Token verification failed completely: {e}")
        raise HTTPException(
            status_code=401, 
            detail="Invalid or expired authentication token. Please sign out and sign back in."
        )
