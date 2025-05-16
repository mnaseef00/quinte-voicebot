from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from twilio_handler import router

# Create FastAPI app
app = FastAPI(title="Quinte Voice Bot")

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

# Include the Twilio router
app.include_router(router, prefix="/api/v1/twilio")

# Root endpoint
@app.get("/")
async def root():
    return {"message": "Quinte Voice Bot API is running"}
