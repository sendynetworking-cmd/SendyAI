import logging
from fastapi import APIRouter, Depends, HTTPException
from ..schemas.profile import ProfileUpdate
from ..core.clients import supabase
from ..core.auth import get_user_id

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/user", tags=["user"])

@router.get("/profile/me")
async def get_profile(user_id: str = Depends(get_user_id)):
    '''
    Fetch existing user profile from Supabase
    '''
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        result = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        if result.data:
            return {"success": True, "profile": result.data}
        return {"success": False, "profile": None}
    except Exception as e:
        logger.info(f"No existing profile found for {user_id}: {e}")
        return {"success": False, "profile": None}

@router.post("/profile")
async def save_profile(profile: ProfileUpdate, user_id: str = Depends(get_user_id)):
    '''
    Save user profile to Supabase
    '''

    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        supabase.table("profiles").upsert({
            "id": user_id,
            "name": profile.name,
            "email": profile.email,
            "university": profile.university,
            "degree": profile.degree,
            "experiences": [exp.dict() for exp in profile.experiences],
            "skills": profile.skills,
            "total_exp": profile.total_exp,
            "raw_summary": profile.raw_summary,
            "updated_at": "now()"
        }).execute()
        return {"success": True}
    except Exception as e:
        logger.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Database save failed")
