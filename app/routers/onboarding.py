import os
import shutil
import tempfile
import logging
import re
import traceback
import pdfplumber
from docx import Document
from fastapi import APIRouter, UploadFile, File, HTTPException
from ..core.clients import nlp
from ..core.config import settings

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/onboarding", tags=["onboarding"])

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

@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    '''
    Parse resume file and extract relevant information
    '''
    
    temp_dir = tempfile.mkdtemp()
    temp_path = os.path.join(temp_dir, file.filename)
    
    try:
        with open(temp_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        
        text = ""
        if file.filename.lower().endswith(".pdf"):
            text = extract_text_from_pdf(temp_path)
        elif file.filename.lower().endswith((".docx", ".doc")):
            text = extract_text_from_docx(temp_path)
        else:
            raise HTTPException(status_code=400, detail="Unsupported file format. Please upload PDF or DOCX.")

        if not text.strip():
            raise ValueError("Could not extract any text from the file.")

        doc = nlp(text) if nlp else None
        
        name = ""
        if doc:
            for ent in doc.ents:
                if ent.label_ == "PERSON" and len(ent.text.split()) >= 2:
                    name = ent.text
                    break
        
        email = ""
        email_match = re.search(r'[\w\.-]+@[\w\.-]+', text)
        if email_match:
            email = email_match.group(0)

        phone = ""
        phone_match = re.search(r'(\+?\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}', text)
        if phone_match:
            phone = phone_match.group(0)

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

        universities = []
        if doc:
            for ent in doc.ents:
                if ent.label_ == "ORG" and any(term in ent.text for term in ["University", "College", "Institute", "School", "Polytechnic"]):
                    if ent.text not in universities:
                        universities.append(ent.text)
        
        degrees = []
        COMMON_DEGREES = ["Bachelor", "Master", "PhD", "B.Sc", "M.Sc", "B.A", "M.A", "B.Tech", "M.Tech", "MBA", "Associate"]
        for d in COMMON_DEGREES:
            if d.lower() in text_lower:
                degrees.append(d)

        COMMON_TITLES = ["Engineer", "Developer", "Manager", "Analyst", "Lead", "Architect", "Scientist", "Consultant", "Designer", "Specialist"]
        
        experiences = []
        if doc:
            date_range_pattern = r'((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|(?:\d{1,2}/\d{2,4}))\s*(?:-|–|to)\s*((?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)[a-z]*\.?\s+\d{4}|(?:\d{1,2}/\d{2,4})|Present|Current)'
            
            lines = text.split('\n')
            current_exp = None
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line: continue
                
                date_match = re.search(date_range_pattern, line, re.IGNORECASE)
                has_title = any(re.search(rf"\b{re.escape(title)}\b", line, re.IGNORECASE) for title in COMMON_TITLES)
                
                if date_match or (has_title and len(line) < 100):
                    if current_exp and (current_exp['title'] or current_exp['company']):
                        experiences.append(current_exp)
                    
                    line_doc = nlp(line)
                    company = ""
                    title = line
                    
                    for ent in line_doc.ents:
                        if ent.label_ == "ORG":
                            company = ent.text
                            title = line.replace(company, "").strip(",- ").strip()
                            break
                    
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
                    if len(current_exp["description"]) < 500:
                        current_exp["description"] += line + " "

            if current_exp and (current_exp['title'] or current_exp['company']):
                experiences.append(current_exp)

        response_data = {
            "name": name,
            "email": email,
            "phone": phone,
            "university": universities[:2],
            "degree": degrees[:2],
            "experiences": experiences[:5],
            "skills": found_skills[:15],
            "total_exp": 0,
            "raw_summary": f"Professional profile with {len(experiences)} roles identified."
        }
        
        logger.info(f"Successfully Super Parsed resume: {name}")
        return response_data

    except Exception as e:
        logger.error(f"Parsing error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
