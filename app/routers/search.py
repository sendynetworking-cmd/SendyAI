import logging
import requests as py_requests
from fastapi import APIRouter, Depends, HTTPException
from ..schemas.profile import SearchRequest
from ..core.clients import supabase
from ..core.auth import get_user_id
from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])

@router.post("/find-email")
async def find_email(req: SearchRequest, user_id: str = Depends(get_user_id)):
    linkedin_url = req.linkedinUrl
    full_name = req.fullName
    company = req.company
    
    if not linkedin_url and not (full_name and company):
        raise HTTPException(status_code=400, detail="Missing Search Parameters")
    
    email = None

    # 1. TRY HUNTER
    hunter_key = settings.HUNTER_API_KEY
    if hunter_key:
        try:
            logger.info(f"Hunter lookup for {full_name} at {company} (URL: {linkedin_url})")
            
            params = {"api_key": hunter_key}
            if full_name and company:
                params["full_name"] = full_name
                params["company"] = company
            elif linkedin_url:
                params["linkedin_url"] = linkedin_url
            
            hunter_url = "https://api.hunter.io/v2/email-finder"
            h_res = py_requests.get(hunter_url, params=params, timeout=10)
            h_data = h_res.json()
            
            if h_data.get("data") and h_data["data"].get("email"):
                email = h_data["data"]["email"]
                logger.info(f"Hunter found email: {email}")
        except Exception as e:
            logger.error(f"Hunter error: {e}")

    # Log usage
    if email:
        try:
            supabase.table("usage_logs").insert({
                "user_id": user_id,
                "action": "find_email",
                "provider": "hunter",
                "success": True,
                "metadata": {"linkedin_url": linkedin_url}
            }).execute()
        except Exception as log_err:
            logger.warning(f"Failed to log search usage: {log_err}")
        
        return {"email": email, "provider": "hunter", "success": True}
    else:
        return {"email": "Not found", "success": False}
