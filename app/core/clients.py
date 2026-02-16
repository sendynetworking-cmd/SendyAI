import logging
from anthropic import Anthropic
from supabase import create_client, Client
from .config import settings

logger = logging.getLogger(__name__)

# Initialize Clients
supabase: Client = None
anthropic_client: Anthropic = None

if not all([settings.SUPABASE_URL, settings.SUPABASE_KEY, settings.ANTHROPIC_API_KEY]):
    logger.error("CRITICAL: Missing required environment variables.")
else:
    try:
        supabase = create_client(settings.SUPABASE_URL, settings.SUPABASE_KEY)
        anthropic_client = Anthropic(api_key=settings.ANTHROPIC_API_KEY)
        logger.info("Clients (Supabase, Anthropic) initialized successfully")
    except Exception as e:
        logger.error(f"Failed to initialize clients: {e}")
