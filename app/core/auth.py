import logging
import requests as py_requests
from fastapi import Header, HTTPException

logger = logging.getLogger(__name__)

async def get_user_id(authorization: str = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing auth token")
    
    # Verify Access Token via Google's UserInfo API
    try:
        userinfo_res = py_requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": authorization}
        )
        if userinfo_res.ok:
            user_data = userinfo_res.json()
            return user_data['sub'] # Unique Google ID
        else:
            logger.warning(f"UserInfo API failed (Status {userinfo_res.status_code}): {userinfo_res.text}")
            raise HTTPException(status_code=401, detail="Invalid or expired token")
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Authentication failed")
