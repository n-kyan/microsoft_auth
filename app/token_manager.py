from msal import PublicClientApplication
import os
from datetime import datetime, timedelta
import requests
from fastapi import HTTPException
import json

class TokenManager:
    def __init__(self):
        self.client_id = os.getenv('OUTLOOK_CLIENT_ID')
        self.authority = "https://login.microsoftonline.com/consumers"
        self.scope = ["Calendars.Read"]
        self.access_token = os.getenv('ACCESS_TOKEN')
        expires_str = os.getenv('TOKEN_EXPIRES')
        self.token_expires = datetime.fromisoformat(expires_str) if expires_str else None
        
        self.app = PublicClientApplication(
            client_id=self.client_id,
            authority=self.authority
        )

    async def get_valid_token(self):
        """Get a valid token"""
        if (self.access_token and self.token_expires 
            and datetime.now() < self.token_expires):
            return self.access_token
        return None

    async def get_auth_url(self):
        """Initialize device flow and return auth URL"""
        flow = self.app.initiate_device_flow(scopes=self.scope)
        
        if "user_code" not in flow:
            raise HTTPException(
                status_code=500,
                detail="Failed to create device flow"
            )
            
        return {
            "verification_uri": flow["verification_uri"],
            "user_code": flow["user_code"],
            "device_code": flow["device_code"],
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
            
            # Instead of saving to file, print the values to add to Render
            print("=== ADD THESE TO RENDER ENVIRONMENT VARIABLES ===")
            print(f"ACCESS_TOKEN={result['access_token']}")
            expires = datetime.now() + timedelta(seconds=result["expires_in"])
            print(f"TOKEN_EXPIRES={expires.isoformat()}")
            print("==============================================")
            
            return {"status": "success", "access_token": result['access_token'], "expires": expires.isoformat()}
            
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