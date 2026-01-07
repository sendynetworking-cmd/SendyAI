import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .routers import onboarding, user, outreach, search

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sendy AI Backend",
    description="Modularized FastAPI backend for Sendy AI LinkedIn Extension",
    version="1.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(onboarding.router)
app.include_router(user.router)
app.include_router(outreach.router)
app.include_router(search.router)

@app.get("/")
async def root():
    return {
        "status": "online", 
        "message": "Sendy AI API (Modular)",
        "version": "1.1.0"
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
