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
        # Initialize device flow
        flow = self.app.initiate_device_flow(scopes=self.scope)
        
        if "user_code" not in flow:
            raise HTTPException(
                status_code=500,
                detail="Failed to create device flow"
            )
            
        # Return both the verification URI and the user code
        return {
            "verification_uri": flow["verification_uri"],
            "user_code": flow["user_code"],
            "device_code": flow["device_code"],  # We'll need this for completing auth
            "expires_in": flow["expires_in"]
        }

    async def complete_device_auth(self, device_code: str):
        try:
            result = self.app.acquire_token_by_device_flow({
                "device_code": device_code,
                "scopes": self.scope
            })
            
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

# Create a singleton instance
token_manager = TokenManager()

def get_token_manager():
    return token_manager