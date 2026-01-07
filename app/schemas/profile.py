from typing import Optional, List
from pydantic import BaseModel

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
    experiences: Optional[List[WorkExperience]] = []
    skills: Optional[List[str]] = []
    total_exp: Optional[float] = 0.0
    raw_summary: Optional[str] = ""

class OutreachRequest(BaseModel):
    profileData: dict

class SearchRequest(BaseModel):
    linkedinUrl: Optional[str] = None
    fullName: Optional[str] = None
    company: Optional[str] = None
