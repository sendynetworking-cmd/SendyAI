import logging
import requests as py_requests
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException, Header
from ..core.clients import supabase
from ..core.auth import get_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/usage", tags=["usage"])

def get_current_monday_utc():
    now = datetime.now(timezone.utc)
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)

@router.get("/status")
async def get_usage_status(
    user_id: str = Depends(get_user_id),
    x_extpay_key: str = Header(None)
):
    '''
    Get current usage status for the authenticated user
    '''
    return await fetch_usage_stats(user_id, x_extpay_key)

async def fetch_usage_stats(user_id: str, extpay_key: str = None):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    monday = get_current_monday_utc()
    
    # 1. Get User Tier from ExtensionPay (Source of Truth)
    tier = "free"
    if extpay_key:
        try:
            # We call ExtensionPay directly to verify the key and get user status
            # ID is 'sendyai' as confirmed by user
            logger.info("[Usage] Verifying ExtensionPay key...")
            ep_url = f"https://extensionpay.com/extension/sendyai/api/v2/user?api_key={extpay_key}"
            response = py_requests.get(ep_url, timeout=5)
            if response.ok:
                logger.info("[Usage] ExtensionPay verification successful")
                data = response.json()
                logger.info("[Usage] ExtensionPay response:", data)
                if data.get("paidAt"):
                    tier = "pro"
            else:
                logger.warning(f"ExtensionPay verification failed: {response.status_code}")
        except Exception as e:
            logger.error(f"Error calling ExtensionPay API: {e}")

    # 2. Query usage_logs for the current week
    usage_res = supabase.table("usage_logs") \
        .select("id", count="exact") \
        .eq("user_id", user_id) \
        .gte("date_accessed", monday.isoformat()) \
        .execute()
    
    count = usage_res.count if usage_res.count is not None else 0
    
    # Tier Limits
    limits = {
        "free": 3,
        "pro": 50
    }
    limit = limits.get(tier, 3)

    return {
        "tier": tier,
        "creditsCount": count,
        "creditsRemaining": max(0, limit - count),
        "limit": limit,
        "lastWeekReset": monday.isoformat()
    }

async def verify_usage(user_id: str, extpay_key: str = None):
    '''
    Helper to check if a user has remaining credits.
    Raises HTTPException if limit reached.
    '''
    stats = await fetch_usage_stats(user_id, extpay_key)
    if stats["creditsRemaining"] <= 0:
        raise HTTPException(
            status_code=403, 
            detail=f"Weekly limit reached ({stats['limit']} credits). Please upgrade or wait for the new week."
        )
    return stats
