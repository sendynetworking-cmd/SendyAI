import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException
from ..schemas.profile import OutreachRequest
from ..core.clients import supabase, genai_client
from ..core.auth import get_user_id
from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/outreach", tags=["outreach"])

@router.post("/generate")
async def generate_outreach(req: OutreachRequest, user_id: str = Depends(get_user_id)):
    logger.info(f"Generating outreach for user: {user_id}")
    if not supabase or not genai_client:
        raise HTTPException(status_code=500, detail="Services not configured")

    try:
        user_profile = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
        if not user_profile.data:
            logger.warning(f"Profile not found for user_id: {user_id}")
            raise HTTPException(status_code=400, detail="User profile not set up. Please complete onboarding in the extension options.")
    except Exception as e:
        logger.error(f"Supabase lookup error for {user_id}: {e}")
        raise HTTPException(status_code=500, detail="Database lookup failed")
    
    user = user_profile.data
    recipient = req.profileData
    
    # Format recipient details for the prompt
    exp_list = "\n".join([f"- {e.get('title')} at {e.get('company')} ({e.get('dates')})" for e in recipient.get('experience', [])])
    edu_list = "\n".join([f"- {e.get('school')}: {e.get('degree')} ({e.get('dates')})" for e in recipient.get('education', [])])
    honors_list = "\n".join([f"- {h.get('title')} from {h.get('issuer')} ({h.get('date')})" for h in recipient.get('honors', [])])

    system_prompt = f"""
    You are an expert networking assistant. Draft a personalized outreach email.
    
    SENDER: {user['name']}
    SENDER BACKGROUND: {user['raw_summary']}
    SENDER SKILLS: {', '.join(user.get('skills', []))}
    
    RECIPIENT: {recipient.get('name')}
    RECIPIENT HEADLINE: {recipient.get('headline')}
    
    RECIPIENT EXPERIENCE:
    {exp_list}
    
    RECIPIENT EDUCATION:
    {edu_list}
    
    RECIPIENT HONORS & AWARDS:
    {honors_list}
    
    Draft an email that builds a meaningful bridge between the SENDER and RECIPIENT. 
    Use specific details from their experience or honors if they are relevant to the sender's background.
    
    Output ONLY the subject and body. No placeholders.
    """

    try:
        response = genai_client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=system_prompt
        )
        
        # Log usage to Supabase
        try:
            supabase.table("usage_logs").insert({
                "user_id": user_id,
                "action": "generate_email",
                "model": settings.GEMINI_MODEL
            }).execute()
        except Exception as log_err:
            logger.warning(f"Failed to log usage: {log_err}")

        return {
            "success": True,
            "email": response.text
        }
    except Exception as e:
        logger.error(f"Generation error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")
