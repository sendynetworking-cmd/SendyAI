import os
import logging
from typing import Optional, List, Any
from fastapi import FastAPI, File, UploadFile, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from google.genai import Client as GenAIClient
from google.genai import types
from google.oauth2 import id_token
from google.auth.transport import requests
import requests as py_requests
from supabase import create_client, Client
from dotenv import load_dotenv
import shutil
import tempfile
import json
import traceback

load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate Essential Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-1.5-flash")

supabase: Optional[Client] = None
genai_client: Optional[GenAIClient] = None

if not SUPABASE_URL: logger.error("MISSING: SUPABASE_URL")
if not SUPABASE_KEY: logger.error("MISSING: SUPABASE_KEY")
if not GEMINI_KEY: logger.error("MISSING: GEMINI_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_KEY]):
    logger.error("CRITICAL: Missing required environment variables. Application will fail on key endpoints.")
else:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
        genai_client = GenAIClient(api_key=GEMINI_KEY)
        logger.info("Clients (Supabase & Gemini) initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")

app = FastAPI(title="Sendy AI Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Models matching resume-parser output
class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    university: Optional[List[str]] = []
    degree: Optional[List[str]] = []
    designition: Optional[List[str]] = []
    skills: Optional[List[str]] = []
    total_exp: Optional[float] = 0.0
    raw_summary: Optional[str] = ""

class OutreachRequest(BaseModel):
    profileData: dict

# Dependency for Auth
async def get_user_id(authorization: Optional[str] = Header(None)):
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing auth token")
    
    token = authorization.replace("Bearer ", "")
    
    # Check if it's an Access Token (starts with ya29) or ID Token
    if token.startswith("ya29."):
        try:
            # Verify Access Token via Google's UserInfo API
            userinfo_res = py_requests.get(
                f"https://www.googleapis.com/oauth2/v3/userinfo?access_token={token}"
            )
            if not userinfo_res.ok:
                raise Exception("Google UserInfo API rejected token")
            
            user_data = userinfo_res.json()
            return user_data['sub'] # Unique Google ID
        except Exception as e:
            logger.error(f"Access token verification failed: {e}")
            raise HTTPException(status_code=401, detail=f"Invalid Access Token: {str(e)}")
    else:
        try:
            # Verify as ID Token (Legacy/Fallback)
            idinfo = id_token.verify_oauth2_token(
                token, 
                requests.Request(), 
                os.getenv("GOOGLE_CLIENT_ID")
            )
            return idinfo['sub']
        except Exception as e:
            logger.error(f"Token verification failed: {e}")
            raise HTTPException(status_code=401, detail="Invalid auth token")

@app.get("/")
async def root():
    return {"status": "online", "message": "Sendy AI API"}

@app.post("/onboarding/parse")
async def parse_resume(file: UploadFile = File(...)):
    if not genai_client:
        raise HTTPException(status_code=500, detail="Gemini API is not configured on the server. Please add GEMINI_API_KEY to your Railway environment variables.")
        
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # 1. Extract Text from PDF
        from pypdf import PdfReader
        reader = PdfReader(temp_path)
        text = ""
        for page in reader.pages:
            text += page.extract_text()
            
        if not text.strip():
            raise ValueError("Could not extract text from PDF")

        # 2. Use Gemini to Parse
        prompt = f"""
        Extract the professional profile from this resume text into the following JSON format:
        {{
          "name": "Full Name",
          "email": "Email Address",
          "phone": "Phone Number",
          "university": ["University 1", "University 2"],
          "degree": ["Degree 1", "Degree 2"],
          "designition": ["Role 1", "Role 2"],
          "skills": ["Skill 1", "Skill 2"],
          "total_exp": 5.5,
          "raw_summary": "A brief 2-3 sentence professional bio"
        }}
        
        RESUME TEXT:
        {text}
        """
        
        logger.info(f"Sending prompt to Gemini ({GEMINI_MODEL}) for parsing...")
        # Note: Using the model configured via environment variables
        response = genai_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                response_mime_type="application/json"
            )
        )
        
        try:
            return json.loads(response.text)
        except Exception as json_err:
            logger.error(f"Failed to parse Gemini JSON output: {response.text}")
            raise ValueError("Invalid JSON format from AI")
        
    except Exception as e:
        logger.error(f"Parsing error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir)

@app.post("/user/profile")
async def save_profile(profile: ProfileUpdate, user_id: str = Depends(get_user_id)):
    if not supabase:
        raise HTTPException(status_code=500, detail="Supabase not configured")
    try:
        supabase.table("profiles").upsert({
            "id": user_id,
            "name": profile.name,
            "email": profile.email,
            "phone": profile.phone,
            "university": profile.university,
            "degree": profile.degree,
            "designition": profile.designition,
            "skills": profile.skills,
            "total_exp": profile.total_exp,
            "raw_summary": profile.raw_summary,
            "updated_at": "now()"
        }).execute()
        return {"success": True}
    except Exception as e:
        logger.error(f"Supabase error: {e}")
        raise HTTPException(status_code=500, detail="Database save failed")

@app.post("/outreach/generate")
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

    system_prompt = f"""
    You are an expert networking assistant. Draft an outreach email.
    
    SENDER: {user['name']}
    SENDER BACKGROUND: {user['raw_summary']}
    SENDER SKILLS: {', '.join(user.get('skills', []))}
    
    RECIPIENT: {recipient.get('name')}
    RECIPIENT ROLE: {recipient.get('headline')}
    
    Output ONLY the subject and body. No placeholders.
    """

    try:
        response = genai_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=system_prompt
        )
        
        # Log usage to Supabase
        try:
            supabase.table("usage_logs").insert({
                "user_id": user_id,
                "action": "generate_email",
                "model": GEMINI_MODEL
            }).execute()
        except Exception as log_err:
            logger.warning(f"Failed to log usage: {log_err}")

        return {
            "success": True,
            "email": response.text,
            "model": GEMINI_MODEL
        }
    except Exception as e:
        logger.error(f"Generation error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=f"AI generation failed: {str(e)}")

@app.post("/api/find-email")
async def find_email(req: dict, user_id: str = Depends(get_user_id)):
    linkedin_url = req.get("linkedinUrl")
    if not linkedin_url:
        raise HTTPException(status_code=400, detail="Missing LinkedIn URL")
    
    email = None

    # 1. TRY HUNTER
    hunter_key = os.getenv("HUNTER_API_KEY")
    if hunter_key:
        try:
            logger.info(f"Attempting Hunter lookup for {linkedin_url}")
            hunter_url = f"https://api.hunter.io/v2/email-finder?linkedin_url={linkedin_url}&api_key={hunter_key}"
            h_res = py_requests.get(hunter_url, timeout=10)
            h_data = h_res.json()
            
            if h_data.get("data") and h_data["data"].get("email"):
                email = h_data["data"]["email"]
        except Exception as e:
            logger.error(f"Hunter error: {e}")

    # Log usage
    if email:
        supabase.table("usage_logs").insert({
            "user_id": user_id,
            "action": "find_email",
            "provider": "hunter",
            "success": True,
            "metadata": {"linkedin_url": linkedin_url}
        }).execute()
        return {"email": email, "provider": "hunter", "success": True}
    else:
        return {"email": "Not found", "success": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
