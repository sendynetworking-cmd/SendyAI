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

@app.middleware("http")
async def log_requests(request, call_next):
    # Log full URL with query params
    logger.info(f"Incoming Request: {request.method} {request.url}")
    
    # Log body for POST/PUT/PATCH
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()
        logger.info(f"Request Body: {body.decode('utf-8')}")
        # Re-set body so it can be read again by the router
        async def receive():
            return {"type": "http.request", "body": body}
        request._receive = receive

    response = await call_next(request)
    logger.info(f"Response Status: {response.status_code}")
    return response

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
