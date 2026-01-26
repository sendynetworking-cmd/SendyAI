import logging
import traceback
from fastapi import APIRouter, Depends, HTTPException, Header
from .usage import verify_usage
from ..schemas.profile import OutreachRequest
from ..core.clients import supabase, genai_client
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
    
    # Check Usage First
    await verify_usage(user_id, x_extpay_key)
    
    if not supabase or not genai_client:
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

    system_prompt = f"""
    You are an expert networking assistant. You help high-achieving students draft initial outreach emails to busy professionals in finance, consulting, tech, and law.

GENERAL STYLE RULES:
- Audience: Busy professionals. Time is money.
- Tone: Authentic, high-achieving student. Polite, confident, not desperate.
- STATUS AWARENESS: You are a student reaching out to a mentor. Avoid "Peer-Talk." Do not speak as if you have the same professional capacity or aptitude as the recipient.
- NEUTRAL SELF-PRESENTATION: When describing the student's background, use neutral, factual language. Avoid self-aggrandizing descriptors like "extensive," "deep," "expert," or "significant." (e.g., use "my background in research" instead of "my extensive research").
- SUCCINCTNESS IS KEY: Be concise. Get to the point immediately.
- PUNCHY PHRASING: Drop fluff words. Avoid empty jargon like "landscapes," "strategic insights," or "nuanced perspectives." Use raw and direct terms (e.g., "geopolitics" instead of "geopolitical landscape").
- NATURAL LANGUAGE: Write like a human. Use "someone" instead of "an individual" or "a professional." 
- NO Generic Flattery: Never use phrases like "I have always admired..." or "It is inspiring to see..."
- Realism: Never fabricate facts. Make reasonable inferences based on the student's actual experience.

⚠️ CRITICAL OUTPUT RULE:
Output ONLY the raw email text. DO NOT include any structural labels or markers (e.g., "SUBJECT LINE:", "PARAGRAPH 1:").

YOUR TASK:
Perform a two-step process internally, then output ONLY the final email text with NO LABELS.

STEP 1 - ANALYZE CONTEXT (Internal):
1) INFER INTERESTS: Lightly infer the student's specific interest based on their past roles.
2) IDENTIFY THE BRIDGE: Select the SINGLE strongest narrative hook (Exact or Thematic match).

STEP 2 - WRITE EMAIL (Output ONLY the final text):

Start with the subject line on its own line:
Reaching Out – [connection snippet] Interested in [their current company]
- Make sure the connection snippet is accurate to whether the user is a student or an alumni/professional. 

Then a blank line, then:
Hi {recipientFirstName},

First paragraph (The Hook):
- "Hope you are doing well."
- Introduce yourself (name, school, major/year, key status).
- Sentence 3: Follow this format: "I came across your profile while researching [Their Company] and..." then complete the sentence by highlighting a **succinct thematic combination** or specific pivot. 
- Constraint: Keep it succinct. Do NOT list their entire resume path.

Second paragraph (The Meat):
- 1-2 succinct sentences connecting your background to that specific theme.
- Ask a PERSONAL career decision question tied to that theme.
- **CONSTRAINT (Substance Over Status):** Do NOT list their past employers/companies just to prove you did research. Only reference past roles if they are the *subject* of the transition question.
- End with: "Would you be available for a quick call to share your perspective?"

Third paragraph (The Narrative Bridge):
- Use the strongest shared attribute/connection.
- **FOUNDATION VS. DESTINATION RULE (Anti-Conceit):** 
  - The "shared" part must be the **Foundation** (what you both have in common: a school, a major, or a raw subject matter interest like "geopolitics" or "history").
  - The "aspirational" part must be the **Destination** (the recipient's current role/field, job function or professional application).
- **NEVER** claim a shared interest in the recipient's job function or professional application (e.g., avoid "shared interest in applying analysis to themes").  - DO say: "Given our shared interest in [Foundation], it would be great to connect with **someone** applying that background to [Destination]..." 
- FLOW CHECK: If this attribute was mentioned in Para 2, use a transitional phrase (e.g., "Given that shared background in...").
- **CORRECT FORMAT:** "Given our shared interest in [Foundation], it would be great to connect with **someone** applying that background to [Destination]."
- End with exactly: "I've attached my resume in case it's helpful background."

Fourth paragraph (Closing):
I look forward to hearing back from you!

Sign off with:
Best,
{studentName}
{userData.school} {gradYear}"""

    try:
        response = genai_client.models.generate_content(
            model=settings.GEMINI_MODEL,
            contents=system_prompt
        )
        
        # Log usage to Supabase
        try:
            supabase.table("usage_logs").insert({
                "user_id": user_id,
                "action": "generate_email"
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
