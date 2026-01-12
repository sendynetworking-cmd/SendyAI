import logging
import traceback
import requests as py_requests
from .usage import verify_usage
from ..schemas.profile import SearchRequest
from ..core.clients import supabase
from ..core.auth import get_user_id
from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api", tags=["search"])

@router.post("/find-email")
async def find_email(
    req: SearchRequest, 
    user_id: str = Depends(get_user_id),
    x_extpay_key: str = Header(None)
):
    '''
    Find email address for a given LinkedIn URL or full name and company
    '''
    
    # Check Usage First
    if not req.skipLog:
        await verify_usage(user_id, x_extpay_key)
    
    logger.info(f"DEBUG: Entering find_email for user {user_id}")
    linkedin_url = req.linkedinUrl
    full_name = req.fullName
    company = req.company
    logger.info(f"DEBUG: Params received: url={linkedin_url}, name={full_name}, company={company}")
    
    if not linkedin_url and not (full_name and company):
        logger.warning("DEBUG: Missing search parameters - returning 400")
        raise HTTPException(status_code=400, detail="Missing Search Parameters")
    
    email = None

    # 1. ATTEMPT 1: HUNTER WITH LINKEDIN HANDLE
    hunter_key = settings.HUNTER_API_KEY
    if hunter_key:
        try:
            # First attempt parameters
            params1 = {"api_key": hunter_key}
            
            # Extract handle from URL if present
            handle = None
            if linkedin_url:
                parts = [p for p in linkedin_url.split('/') if p]
                if 'in' in parts:
                    idx = parts.index('in')
                    if idx + 1 < len(parts):
                        handle = parts[idx + 1]
            
            if handle:
                params1["linkedin_handle"] = handle
                logger.info(f"DEBUG: Attempt 1 - Using LinkedIn Handle: {handle}")
                
                logger.info("DEBUG: Calling Hunter.io API (Attempt 1)...")
                h_res = py_requests.get("https://api.hunter.io/v2/email-finder", params=params1, timeout=10)
                logger.info(f"DEBUG: Attempt 1 Response Status: {h_res.status_code}")
                
                h_data = h_res.json()
                if h_data.get("data") and h_data["data"].get("email"):
                    email = h_data["data"]["email"]
                    logger.info(f"Hunter found email in Attempt 1: {email}")
                else:
                    logger.info("DEBUG: Attempt 1 failed or returned no email.")
            
            # 2. ATTEMPT 2: FALLBACK TO FULL NAME + COMPANY
            if not email and full_name and company:
                params2 = {
                    "api_key": hunter_key,
                    "full_name": full_name,
                    "company": company
                }
                logger.info(f"DEBUG: Attempt 2 - Using Name/Company Search: {full_name} @ {company}")
                
                logger.info("DEBUG: Calling Hunter.io API (Attempt 2)...")
                h_res = py_requests.get("https://api.hunter.io/v2/email-finder", params=params2, timeout=10)
                logger.info(f"DEBUG: Attempt 2 Response Status: {h_res.status_code}")
                
                h_data = h_res.json()
                if h_data.get("data") and h_data["data"].get("email"):
                    email = h_data["data"]["email"]
                    logger.info(f"Hunter found email in Attempt 2: {email}")
                else:
                    logger.info("DEBUG: Attempt 2 failed or returned no email.")

        except Exception as e:
            logger.error(f"Hunter integration error: {e}")
            logger.error(traceback.format_exc())

    # Log usage
    if email and not req.skipLog:
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
