import logging
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Depends, HTTPException
from ..core.clients import supabase
from ..core.auth import get_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/usage", tags=["usage"])

def get_current_monday_utc():
    now = datetime.now(timezone.utc)
    # weekday() returns 0 for Monday, 6 for Sunday
    monday = now - timedelta(days=now.weekday())
    return monday.replace(hour=0, minute=0, second=0, microsecond=0)

@router.get("/status")
async def get_usage_status(user_id: str = Depends(get_user_id)):
    '''
    Get current usage status for the authenticated user
    '''
    return await fetch_usage_stats(user_id)

async def fetch_usage_stats(user_id: str):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")

    monday = get_current_monday_utc()
    
    # 1. Get User Tier
    tier = "free"
    try:
        profile_res = supabase.table("profiles").select("tier").eq("id", user_id).single().execute()
        if profile_res.data:
            tier = profile_res.data.get("tier", "free")
    except Exception:
        # Fallback to free if profile check fails (might be a new user)
        pass

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

async def verify_usage(user_id: str):
    '''
    Helper to check if a user has remaining credits.
    Raises HTTPException if limit reached.
    '''
    stats = await fetch_usage_stats(user_id)
    if stats["creditsRemaining"] <= 0:
        raise HTTPException(
            status_code=403, 
            detail=f"Weekly limit reached ({stats['limit']} credits). Please upgrade or wait for the new week."
        )
    return stats
