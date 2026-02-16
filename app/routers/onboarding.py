import os
import shutil
import tempfile
import logging
import json
import re
import traceback
import pdfplumber
from docx import Document
from fastapi import APIRouter, UploadFile, File, HTTPException
from ..core.clients import anthropic_client
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
    Parse resume file and extract relevant information using Claude
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

        # Use Claude for Parsing
        if not anthropic_client:
            raise HTTPException(status_code=500, detail="Anthropic client not initialized")

        prompt = f"""
        Analyze the following resume text and extract information into a VALID JSON format.
        
        REQUIRED JSON STRUCTURE:
        {{
            "name": "Full Name",
            "email": "Email Address",
            "university": ["List of Universities"],
            "degree": ["List of Degrees"],
            "skills": ["List of Professional Skills"],
            "experiences": [
                {{
                    "title": "Job Title",
                    "company": "Company Name",
                    "start_date": "Start Date",
                    "end_date": "End Date or Present",
                    "description": "Short description"
                }}
            ]
        }}

        RESUME TEXT:
        {text[:10000]}
        """

        try:
            response = anthropic_client.messages.create(
                model=settings.ANTHROPIC_MODEL,
                max_tokens=2048,
                system="You are a resume parser. Output only valid JSON, no other text.",
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            # Extract JSON from response
            raw_response = response.content[0].text
            json_match = re.search(r'\{.*\}', raw_response, re.DOTALL)
            if json_match:
                parsed_data = json.loads(json_match.group(0))
            else:
                logger.error(f"Claude failed to return JSON. Raw response: {raw_response}")
                raise ValueError("AI failed to parse resume structure")

            # Final response mapping with fallbacks
            response_data = {
                "name": parsed_data.get("name", ""),
                "email": parsed_data.get("email", ""),
                "university": parsed_data.get("university", []),
                "degree": parsed_data.get("degree", []),
                "experiences": parsed_data.get("experiences", []),
                "skills": parsed_data.get("skills", []),
                "total_exp": 0,
                "raw_summary": f"Professional profile with {len(parsed_data.get('experiences', []))} roles identified."
            }
            
            logger.info(f"Successfully parsed resume for: {response_data['name']}")
            return response_data

        except Exception as e:
            logger.error(f"Claude parsing error: {e}")
            raise HTTPException(status_code=500, detail="AI parsing failed")

    except Exception as e:
        logger.error(f"General parsing error: {e}")
        logger.error(traceback.format_exc())
        raise HTTPException(status_code=500, detail=str(e))
    finally:
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)
