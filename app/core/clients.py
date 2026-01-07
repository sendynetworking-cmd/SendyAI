import logging
import spacy
from google.genai import Client as GenAIClient
from supabase import create_client, Client
from .config import settings

logger = logging.getLogger(__name__)

# Initialize Spacy
try:
    nlp = spacy.load("en_core_web_sm")
    logger.info("Spacy model 'en_core_web_sm' loaded successfully")
except Exception as e:
    logger.error(f"Failed to load Spacy model: {e}")
    nlp = None

# Initialize Clients
supabase: Client = None
genai_client: GenAIClient = None

if not all([settings.SUPABASE_URL, settings.SUPABASE_KEY, settings.GEMINI_API_KEY]):
    logger.error("CRITICAL: Missing required environment variables.")
else:
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        genai_client = GenAIClient(api_key=settings.GEMINI_API_KEY)
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
