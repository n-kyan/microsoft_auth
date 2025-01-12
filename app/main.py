from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from datetime import datetime, timedelta
import uvicorn
from .token_manager import TokenManager, get_token_manager

app = FastAPI()

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with your Streamlit app URL in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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

@app.post("/auth/initialize")
async def initialize_auth(
    token_manager: TokenManager = Depends(get_token_manager)
):
    auth_url = await token_manager.get_auth_url()
    return {"auth_url": auth_url}

@app.post("/auth/complete")
async def complete_auth(
    code: str,
    token_manager: TokenManager = Depends(get_token_manager)
):
    return await token_manager.complete_auth(code)

if __name__ == "__main__":
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)

# app/token_manager.py
from msal import PublicClientApplication
import os
from datetime import datetime, timedelta
import requests
from fastapi import HTTPException
import json
from pathlib import Path

class TokenManager:
    def __init__(self):
        self.client_id = os.getenv('OUTLOOK_CLIENT_ID')
        self.authority = "https://login.microsoftonline.com/consumers"
        self.scope = ["Calendars.Read"]
        self.token_path = Path("token_cache.json")
        self.access_token = None
        self.token_expires = None
        
        self.app = PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority
        )
        
        # Load cached token if exists
        self._load_token_cache()

    def _load_token_cache(self):
        if self.token_path.exists():
            try:
                with open(self.token_path, 'r') as f:
                    cache_data = json.load(f)
                    self.access_token = cache_data.get('access_token')
                    expires_str = cache_data.get('expires')
                    if expires_str:
                        self.token_expires = datetime.fromisoformat(expires_str)
            except Exception:
                self.access_token = None
                self.token_expires = None

    def _save_token_cache(self):
        cache_data = {
            'access_token': self.access_token,
            'expires': self.token_expires.isoformat() if self.token_expires else None
        }
        with open(self.token_path, 'w') as f:
            json.dump(cache_data, f)

    async def get_valid_token(self):
        if (self.access_token and self.token_expires 
            and datetime.now() < self.token_expires):
            return self.access_token
        return None

    async def get_auth_url(self):
        # Generate the authorization URL
        auth_url = self.app.get_authorization_request_url(
            scopes=self.scope,
            redirect_uri="your-render-url/auth/callback"  # Update with actual URL
        )
        return auth_url

    async def complete_auth(self, auth_code: str):
        try:
            result = self.app.acquire_token_by_authorization_code(
                code=auth_code,
                scopes=self.scope,
                redirect_uri="your-render-url/auth/callback"  # Update with actual URL
            )
            
            if "access_token" not in result:
                raise HTTPException(
                    status_code=400, 
                    detail=f"Failed to acquire token: {result.get('error_description', 'Unknown error')}"
                )
            
            self.access_token = result["access_token"]
            self.token_expires = datetime.now() + timedelta(seconds=result["expires_in"])
            self._save_token_cache()
            
            return {"status": "success"}
            
        except Exception as e:
            raise HTTPException(status_code=400, detail=str(e))

    async def get_calendar_events(self, start_date: datetime, end_date: datetime):
        if not self.access_token:
            raise HTTPException(status_code=401, detail="No valid token")
            
        headers = {
            'Authorization': f'Bearer {self.access_token}',
            'Content-Type': 'application/json'
        }

        url = 'https://graph.microsoft.com/v1.0/me/calendarView'
        params = {
            'startDateTime': start_date.isoformat() + 'Z',
            'endDateTime': end_date.isoformat() + 'Z',
            '$select': 'subject,start,end,showAs'
        }

        response = requests.get(url, headers=headers, params=params)
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=response.text
            )
            
        return response.json()

def get_token_manager():
    return TokenManager()