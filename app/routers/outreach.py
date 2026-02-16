import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException, Header
from .usage import verify_usage
from ..schemas.profile import OutreachRequest
from ..core.clients import supabase, anthropic_client
from ..core.auth import get_user_id
from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/outreach", tags=["outreach"])

@router.post("/generate")
async def generate_outreach(
    req: OutreachRequest, 
    user_id: str = Depends(get_user_id),
    x_extpay_key: str = Header(None)
):
    '''
    Generate outreach email for a given recipient profile
    '''
    
    if not supabase or not anthropic_client:
        raise HTTPException(status_code=500, detail="Services not configured")

    # Lookup user profile
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
    
    exp_list = "\n".join([f"- {e.get('title')} at {e.get('company')} ({e.get('dates')})" for e in recipient.get('experience', [])])
    edu_list = "\n".join([f"- {e.get('school')}: {e.get('degree')} ({e.get('dates')})" for e in recipient.get('education', [])])
    honors_list = "\n".join([f"- {h.get('title')} from {h.get('issuer')} ({h.get('date')})" for h in recipient.get('honors', [])])

    recipient_first_name = (recipient.get("name") or "").strip().split(" ")[0] or "there"

    system_prompt = f"""
    You are an expert networking assistant. You help high-achieving students draft initial outreach emails to busy professionals in finance, consulting, tech, and law.

    CONTEXT (DO NOT IGNORE):
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

    GENERAL STYLE RULES:
    - Audience: Busy professionals. Time is money.
    - Tone: Authentic, high-achieving student. Polite, confident, not desperate.
    - STATUS AWARENESS: You are a student reaching out to a mentor. Avoid "Peer-Talk." Do not speak as if you have the same professional capacity or aptitude as the recipient.
    - NEUTRAL SELF-PRESENTATION: When describing the student's background, use neutral, factual language. Avoid self-aggrandizing descriptors like "extensive," "deep," "expert," or "significant."
    - SUCCINCTNESS IS KEY: Be concise. Get to the point immediately.
    - PUNCHY PHRASING: Drop fluff words. Avoid empty jargon like "landscapes," "strategic insights," or "nuanced perspectives."
    - NATURAL LANGUAGE: Write like a human. Use "someone" instead of "an individual" or "a professional."
    - NO Generic Flattery: Never use phrases like "I have always admired..." or "It is inspiring to see..."
    - Realism: Never fabricate facts. Make reasonable inferences based on the student's actual experience.

    ⚠️ CRITICAL OUTPUT RULE:
    Output ONLY the raw email text. DO NOT include any structural labels or markers (e.g., "SUBJECT LINE:", "PARAGRAPH 1:").
    Output ONLY the final email text (subject line + body). No placeholders.
    """

    user_message = f"""
    YOUR TASK:
    Perform a two-step process internally, then output ONLY the final email text with NO LABELS.

    STEP 1 - ANALYZE CONTEXT (Internal):
    1) INFER INTERESTS: Lightly infer the student's specific interest based on their background and skills.
    2) IDENTIFY THE BRIDGE: Select the SINGLE strongest narrative hook (Exact or Thematic match) using recipient experience/education/honors ONLY if relevant.

    STEP 2 - WRITE EMAIL (Output ONLY the final text):

    Start with the subject line on its own line:
    Reaching Out – [connection snippet] Interested in [their current company]
    - Make sure the connection snippet is accurate to whether the sender is a student.

    Then a blank line, then:
    Hi {recipient_first_name},

    First paragraph (The Hook):
    - Include the phrase: "Hope you are doing well."
    - Introduce yourself (name + key student status from SENDER BACKGROUND; do NOT invent school/major/year if not present).
    - Sentence 3 must follow this format exactly:
    "I came across your profile while researching [Their Company] and..." then finish by highlighting a succinct thematic combination or specific pivot.
    - Keep it succinct. Do NOT list their entire resume path.

    Second paragraph (The Meat):
    - 1-2 succinct sentences connecting SENDER BACKGROUND/SKILLS to that specific theme.
    - Ask a personal career decision question tied to that theme.
    - Do NOT list their past employers/companies just to prove you did research. Only reference past roles if they are the subject of the transition question.
    - End with exactly: "Would you be available for a quick call to share your perspective?"

    Third paragraph (The Narrative Bridge):
    - Use the strongest shared attribute/connection drawn from the provided context.
    - FOUNDATION VS. DESTINATION RULE:
    - Foundation: common school, major/field, or raw subject interest.
    - Destination: recipient's current role/field/job function/professional application.
    - Use this exact sentence structure:
    "Given our shared interest in [Foundation], it would be great to connect with someone applying that background to [Destination]."
    - End with exactly: "I've attached my resume in case it's helpful background."

    Fourth paragraph (Closing):
    I look forward to hearing back from you!

    Best,
    {user['name']}
    """

    try:
        response = anthropic_client.messages.create(
            model=settings.ANTHROPIC_MODEL,
            max_tokens=1024,
            system=system_prompt,
            messages=[
                {"role": "user", "content": user_message}
            ]
        )
        
        return {
            "success": True,
            "email": response.content[0].text
        }
    except Exception as e:
        logger.error(f"Generation error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")
