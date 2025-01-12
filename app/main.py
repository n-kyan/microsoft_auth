from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import uvicorn
from app.token_manager import TokenManager, get_token_manager
from pydantic import BaseModel

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class DeviceCode(BaseModel):
    device_code: str

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.get("/calendar/available-slots")
async def get_available_slots(
    date: str,
    token_manager: TokenManager = Depends(get_token_manager)
):
    token = await token_manager.get_valid_token()
    if not token:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    try:
        date_obj = datetime.strptime(date, '%Y-%m-%d')
        start_of_day = datetime.combine(date_obj, datetime.min.time())
        end_of_day = datetime.combine(date_obj, datetime.max.time())
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date format")
    
    return await token_manager.get_calendar_events(start_of_day, end_of_day)

@app.get("/auth/initialize")
async def initialize_auth(
    token_manager: TokenManager = Depends(get_token_manager)
):
    return await token_manager.get_auth_url()

@app.post("/auth/complete")
async def complete_auth(
    device_code: DeviceCode,
    token_manager: TokenManager = Depends(get_token_manager)
):
    return await token_manager.complete_device_auth(device_code.device_code)

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)