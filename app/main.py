import logging
import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from .routers import onboarding, user, outreach, search, usage

# Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Sendy AI Backend",
    description="Modularized FastAPI backend for Sendy AI LinkedIn Extension",
    version="1.1.0"
)

@app.middleware("http")
async def log_requests(request, call_next):
    # Log full URL with query params
    logger.info(f"Incoming Request: {request.method} {request.url}")
    logger.info(f"Headers: x-extpay-key={request.headers.get('x-extpay-key')}, auth={bool(request.headers.get('Authorization'))}")
    
    # Log body for POST/PUT/PATCH
    if request.method in ["POST", "PUT", "PATCH"]:
        body = await request.body()
        try:
            decoded_body = body.decode('utf-8')
            logger.info(f"Request Body: {decoded_body}")
        except UnicodeDecodeError:
            logger.info("Request Body: <binary data>")
        
        # Re-set body so it can be read again by the router
        async def receive():
            return {"type": "http.request", "body": body}
        request._receive = receive

    response = await call_next(request)
    logger.info(f"Response Status: {response.status_code}")
    return response

# CORS - Must be added AFTER other middlewares to be the outermost layer
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:8000",
        "chrome-extension://cljgofleblhgmbhgloagholbpojhflja"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(onboarding.router)
app.include_router(user.router)
app.include_router(outreach.router)
app.include_router(search.router)
app.include_router(usage.router)

# Serve Static Files (CSS, JS, etc.)
static_path = os.path.join(os.path.dirname(__file__), "static")
app.mount("/static", StaticFiles(directory=static_path), name="static")

@app.get("/")
async def root():
    # Serve index.html (renamed home.html) at the root
    return FileResponse(os.path.join(static_path, "index.html"))

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)
