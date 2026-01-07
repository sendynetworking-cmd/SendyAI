import os
import logging
from typing import Optional, List, Any
from fastapi import FastAPI, File, UploadFile, Header, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from resume_parser import resumeparse
import google.generativeai as genai
from google.oauth2 import id_token
from google.auth.transport import requests
import requests as py_requests
from supabase import create_client, Client
from dotenv import load_dotenv
import shutil
import tempfile

load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Validate Essential Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")

if not all([SUPABASE_URL, SUPABASE_KEY, GEMINI_KEY]):
    logger.error("CRITICAL: Missing required environment variables (SUPABASE_URL, SUPABASE_KEY, or GEMINI_API_KEY)")
    # We don't exit here to allow help check / etc, but we'll error on requests
    supabase = None
    genai_configured = False
else:
    try:
        supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)
        genai.configure(api_key=GEMINI_KEY)
        genai_configured = True
        logger.info("Clients initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
        supabase = None
        genai_configured = False

app = FastAPI(title="Sendy AI Backend")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ... rest of the app initialization ...

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
    try:
        # Verify the Google Token
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            os.getenv("GOOGLE_CLIENT_ID")
        )

        # The 'sub' field is the unique Google User ID
        return idinfo['sub']
    except Exception as e:
        logger.error(f"Token verification failed: {e}")
        raise HTTPException(status_code=401, detail="Invalid auth token")

@app.get("/")
async def root():
    return {"status": "online", "message": "Sendy AI API"}

@app.post("/onboarding/parse")
async def parse_resume(file: UploadFile = File(...)):
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    
    with open(temp_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    try:
        # Using the resume-parser library as requested
        data = resumeparse.read_file(temp_path)
        logger.info(f"Parsed data: {data}")
        return data
    except Exception as e:
        logger.error(f"Parsing error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        shutil.rmtree(temp_dir)

@app.post("/user/profile")
async def save_profile(profile: ProfileUpdate, user_id: str = Depends(get_user_id)):
    try:
        data = supabase.table("profiles").upsert({
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
    user_profile = supabase.table("profiles").select("*").eq("id", user_id).single().execute()
    if not user_profile.data:
        raise HTTPException(status_code=400, detail="User profile not set up")
    
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
        model = genai.GenerativeModel('gemini-1.5-flash')
        # ... generation logic ...
        response = model.generate_content(system_prompt)
        
        supabase.table("usage_logs").insert({
            "user_id": user_id,
            "action": "generate_email",
            "model": "gemini-1.5-flash"
        }).execute()
        
        return {
            "success": True,
            "email": response.text,
            "model": "gemini-1.5-flash"
        }
    except Exception as e:
        logger.error(f"Generation error: {e}")
        raise HTTPException(status_code=500, detail="AI generation failed")

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
