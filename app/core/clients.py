import logging
from google.genai import Client as GenAIClient
from supabase import create_client, Client
from supabase.lib.client_options import ClientOptions
from .config import settings

logger = logging.getLogger(__name__)

# Initialize Clients
supabase: Client = None
genai_client: GenAIClient = None

if not all([settings.SUPABASE_URL, settings.SUPABASE_KEY, settings.GEMINI_API_KEY]):
    logger.error("CRITICAL: Missing required environment variables.")
else:
    try:
        # Use ClientOptions to enable async mode
        supabase = create_client(
            settings.SUPABASE_URL, 
            settings.SUPABASE_KEY,
            options=ClientOptions(is_async=True)
        )
        genai_client = GenAIClient(api_key=settings.GEMINI_API_KEY)
        logger.info("Clients (Supabase, GenAI) initialized successfully in Async mode")
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
