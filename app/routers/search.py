import logging
import traceback
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
    '''
    Find email address for a given LinkedIn URL or full name and company
    '''
    
    logger.info(f"DEBUG: Entering find_email for user {user_id}")
    linkedin_url = req.linkedinUrl
    full_name = req.fullName
    company = req.company
    logger.info(f"DEBUG: Params received: url={linkedin_url}, name={full_name}, company={company}")
    
    if not linkedin_url and not (full_name and company):
        logger.warning("DEBUG: Missing search parameters - returning 400")
        raise HTTPException(status_code=400, detail="Missing Search Parameters")
    
    email = None

    # 1. TRY HUNTER
    hunter_key = settings.HUNTER_API_KEY
    if hunter_key:
        try:
            params = {"api_key": hunter_key}
            
            # Extract handle from URL if present
            handle = None
            if linkedin_url:
                # e.g. https://www.linkedin.com/in/username/ -> username
                parts = [p for p in linkedin_url.split('/') if p]
                if 'in' in parts:
                    idx = parts.index('in')
                    if idx + 1 < len(parts):
                        handle = parts[idx + 1]
            
            if handle:
                params["linkedin_handle"] = handle
                logger.info(f"DEBUG: Using LinkedIn Handle: {handle}")
            elif full_name and company:
                params["full_name"] = full_name
                params["company"] = company
                logger.info(f"DEBUG: Using Name/Company Search: {full_name} @ {company}")
            else:
                logger.warning("DEBUG: Not enough data for Hunter lookup")
                return {"email": "Not found", "success": False}

            logger.info(f"DEBUG: Final Hunter.io Parameters: {params}")
            
            logger.info("DEBUG: Calling Hunter.io API...")
            hunter_url = "https://api.hunter.io/v2/email-finder"
            h_res = py_requests.get(hunter_url, params=params, timeout=10)
            logger.info(f"DEBUG: Full Hunter URL hit: {h_res.url}")
            logger.info(f"DEBUG: Hunter Response Status: {h_res.status_code}")
            
            h_data = h_res.json()
            logger.info(f"DEBUG: Hunter Data Payload: {h_data}")
            
            if h_data.get("data") and h_data["data"].get("email"):
                email = h_data["data"]["email"]
                logger.info(f"Hunter found email: {email}")
            elif h_data.get("errors"):
                logger.error(f"Hunter API Errors: {h_data['errors']}")
        except Exception as e:
            logger.error(f"Hunter integration error: {e}")
            logger.error(traceback.format_exc())

    # Log usage
    if email:
        try:
            supabase.table("usage_logs").insert({
                "user_id": user_id,
                "action": "find_email"
            }).execute()
        except Exception as log_err:
            logger.warning(f"Failed to log search usage: {log_err}")
        
        return {"email": email, "provider": "hunter", "success": True}
    else:
        return {"email": "Not found", "success": False}
