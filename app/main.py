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
import re
import spacy
import pdfplumber
from docx import Document

load_dotenv()

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Initialize Spacy 3
try:
    nlp = spacy.load("en_core_web_sm")
    logger.info("Spacy model 'en_core_web_sm' loaded successfully")
except Exception as e:
    logger.error(f"Failed to load Spacy model: {e}")
    nlp = None

def extract_text_from_pdf(path):
    text = ""
    try:
        with pdfplumber.open(path) as pdf:
            for page in pdf.pages:
                page_text = page.extract_text()
                if page_text:
                    text += page_text + "\n"
    except Exception as e:
        logger.error(f"Error extracting PDF text: {e}")
    return text

def extract_text_from_docx(path):
    try:
        doc = Document(path)
        return "\n".join(p.text for p in doc.paragraphs)
    except Exception as e:
        logger.error(f"Error extracting DOCX text: {e}")
        return ""

# Validate Essential Environment Variables
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
GEMINI_KEY = os.getenv("GEMINI_API_KEY")
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.0-flash")

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
        logger.info(f"Clients (Supabase & Gemini {GEMINI_MODEL}) initialized successfully")

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
class WorkExperience(BaseModel):
    title: Optional[str] = ""
    company: Optional[str] = ""
    start_date: Optional[str] = ""
    end_date: Optional[str] = ""
    description: Optional[str] = ""

class ProfileUpdate(BaseModel):
    name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    university: Optional[List[str]] = []
    degree: Optional[List[str]] = []
    designition: Optional[List[str]] = [] # Keeping for backward compatibility
    experiences: Optional[List[WorkExperience]] = []
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
    
    # Try Access Token first (Common for Chrome Extensions)
    try:
        # Verify Access Token via Google's UserInfo API
        userinfo_res = py_requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {token}"}
        )
        if userinfo_res.ok:
            user_data = userinfo_res.json()
            return user_data['sub'] # Unique Google ID
        else:
            logger.warning(f"UserInfo API failed (Status {userinfo_res.status_code}): {userinfo_res.text}")
    except Exception as e:
        logger.error(f"Access token check logic failed: {e}")

    # Fallback/Try ID Token
    try:
        idinfo = id_token.verify_oauth2_token(
            token, 
            requests.Request(), 
            os.getenv("GOOGLE_CLIENT_ID")
        )
        return idinfo['sub']
    except Exception as e:
        logger.error(f"Token verification failed completely: {e}")
        raise HTTPException(
            status_code=401, 
            detail="Invalid or expired authentication token. Please sign out and sign back in."
        )

@app.get("/")
async def root():
    return {"status": "online", "message": "Sendy AI API"}

@app.post("/onboarding/parse")
async def parse_resume(file: UploadFile = File(...)):
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        # 1. Extract raw text based on file type
        text = ""
        if file.filename.lower().endswith(".pdf"):
            text = extract_text_from_pdf(temp_path)
        elif file.filename.lower().endswith((".docx", ".doc")):
            text = extract_text_from_docx(temp_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF or DOCX.")

        if not text.strip():
            raise ValueError("Could not extract any text from the file.")

        # 2. Super Parsing using Spacy 3 and Regex
        doc = nlp(text) if nlp else None
        
        # Name extraction (Heuristic: First Person entity that looks like a name)
        name = ""
        if doc:
            for ent in doc.ents:
                if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                    name = ent.text
                    break
        
        # Email extraction (Regex)
        email = ""
        email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
        if email_match:
            email = email_match.group(0)

        # Phone extraction (Regex)
        phone = ""
        phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
        if phone_match:
            phone = phone_match.group(0)

        # Skills (Keyword matching with modern list)
        COMMON_SKILLS = [
            "Python", "Java", "JavaScript", "TypeScript", "React", "Angular", "Vue", "Node.js", 
            "HTML", "CSS", "SQL", "NoSQL", "PostgreSQL", "MongoDB", "AWS", "Azure", "GCP", 
            "Docker", "Kubernetes", "Git", "CI/CD", "Machine Learning", "Data Analysis", 
            "C++", "C#", "Go", "Rust", "Swift", "Kotlin", "Flutter", "FastAPI", "Django", "Flask",
            "Next.js", "Tailwind", "REST API", "GraphQL", "PyTorch", "TensorFlow", "Pandas", "Scikit-Learn"
        ]
        found_skills = []
        text_lower = text.lower()
        for skill in COMMON_SKILLS:
            if re.search(rf"\b{re.escape(skill.lower())}\b", text_lower):
                found_skills.append(skill)

        # University/Education
        universities = []
        if doc:
            for ent in doc.ents:
                if ent.label_ == "ORG" and any(term in ent.text for term in ["University", "College", "Institute", "School", "Polytechnic"]):
                    if ent.text not in universities:
                        universities.append(ent.text)
        
        # Degree
        degrees = []
        COMMON_DEGREES = ["Bachelor", "Master", "PhD", "B.Sc", "M.Sc", "B.A", "M.A", "B.Tech", "M.Tech", "MBA", "Associate"]
        for d in COMMON_DEGREES:
            if d.lower() in text_lower:
                degrees.append(d)

        # Designation/Roles (Legacy backup)
        designations = []
        COMMON_TITLES = ["Engineer", "Developer", "Manager", "Analyst", "Lead", "Architect", "Scientist", "Consultant", "Designer", "Specialist"]
        
        # 3. Enhanced Experience Extraction (Hierarchical)
        experiences = []
        if doc:
            # Look for experience-like blocks (Title, Company, Date ranges)
            date_range_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|(?:\d{1,2}/\d{2,4}))\s*(?:-|–|to)\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|(?:\d{1,2}/\d{2,4})|Present|Current)'
            
            lines = text.split('\n')
            current_exp = None
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line: continue
                
                # Check for date ranges - often marks a new experience entry
                date_match = re.search(date_range_pattern, line, re.IGNORECASE)
                
                # Check for common titles
                has_title = any(re.search(rf"\b{re.escape(title)}\b", line, re.IGNORECASE) for title in COMMON_TITLES)
                
                if date_match or (has_title and len(line) < 100):
                    # Potential new experience block
                    if current_exp and (current_exp['title'] or current_exp['company']):
                        experiences.append(current_exp)
                    
                    # Try to separate title and company if on same line
                    # Heuristic: Spacy ORG is usually the company
                    line_doc = nlp(line)
                    company = ""
                    title = line
                    
                    for ent in line_doc.ents:
                        if ent.label_ == "ORG":
                            company = ent.text
                            title = line.replace(company, "").strip(",- ").strip()
                            break
                    
                    # If date is in the same line, strip it from title
                    if date_match:
                        title = title.replace(date_match.group(0), "").strip(",- ").strip()
                    
                    current_exp = {
                        "title": title[:100] if title else "Team Member",
                        "company": company[:100] if company else "Company",
                        "start_date": date_match.group(1) if date_match else "",
                        "end_date": date_match.group(2) if date_match else "",
                        "description": ""
                    }
                elif current_exp:
                    # Append to description of the current experience
                    if len(current_exp["description"]) < 500: # Cap description length
                        current_exp["description"] += line + " "

            # Add last one
            if current_exp and (current_exp['title'] or current_exp['company']):
                experiences.append(current_exp)

        # Map to final response
        response_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "university": universities[:2],
            "degree": degrees[:2],
            "designition": [e['title'] for e in experiences[:5]], # Backwards compatibility
            "experiences": experiences[:5], # Limit to top 5
            "skills": found_skills[:15],
            "total_exp": 0,
            "raw_summary": f"Professional profile with {len(experiences)} roles identified."
        }
        
        logger.info(f"Successfully Super Parsed resume: {name} with {len(experiences)} experiences")
        return response_data

    except Exception as e:
        logger.error(f"Parsing error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_dir):
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

    # PRUNING: Avoid 429s by limiting input size
    summary = user.get('raw_summary', '')[:500]
    skills = ', '.join(user.get('skills', [])[:10])
    headline = recipient.get('headline', '')[:150]

    system_prompt = f"""
    Draft a personalized outreach email.
    SENDER: {user['name']}
    SENDER BACKGROUND: {summary}
    SENDER SKILLS: {skills}
    RECIPIENT: {recipient.get('name')}
    RECIPIENT ROLE: {headline}
    Output ONLY THE SUBJECT AND BODY.
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
    full_name = req.get("fullName")
    company = req.get("company")
    
    if not linkedin_url and not (full_name and company):
        raise HTTPException(status_code=400, detail="Missing Search Parameters")
    
    email = None

    # 1. TRY HUNTER
    hunter_key = os.getenv("HUNTER_API_KEY")
    if hunter_key:
        try:
            logger.info(f"Hunter lookup for {full_name} at {company} (URL: {linkedin_url})")
            
            # Prefer Name + Company as per Hunter V2 documentation
            params = {"api_key": hunter_key}
            if full_name and company:
                params["full_name"] = full_name
                params["company"] = company
            elif linkedin_url:
                params["linkedin_url"] = linkedin_url
            
            hunter_url = "https://api.hunter.io/v2/email-finder"
            h_res = py_requests.get(hunter_url, params=params, timeout=10)
            h_data = h_res.json()
            
            if h_data.get("data") and h_data["data"].get("email"):
                email = h_data["data"]["email"]
                logger.info(f"Hunter found email: {email}")
        except Exception as e:
            logger.error(f"Hunter error: {e}")

    # Log usage (wrapped in try-except to avoid failing the whole request)
    if email:
        try:
            supabase.table("usage_logs").insert({
                "user_id": user_id,
                "action": "find_email",
                "provider": "hunter",
                "success": True,
                "metadata": {"linkedin_url": linkedin_url}
            }).execute()
        except Exception as log_err:
            logger.warning(f"Failed to log search usage: {log_err}")
        
        return {"email": email, "provider": "hunter", "success": True}
    else:
        return {"email": "Not found", "success": False}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
