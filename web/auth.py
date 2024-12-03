from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2AuthorizationCodeBearer
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from typing import Optional
import json
import os

# OAuth2 configuration
GOOGLE_CLIENT_CONFIG = {
    "web": {
        "client_id": os.getenv("GOOGLE_CLIENT_ID"),
        "client_secret": os.getenv("GOOGLE_CLIENT_SECRET"),
        "auth_uri": "https://accounts.google.com/o/oauth2/auth",
        "token_uri": "https://oauth2.googleapis.com/token",
        "redirect_uris": ["http://localhost:8000/auth/callback"]
    }
}

SCOPES = [
    'https://www.googleapis.com/auth/spreadsheets',
    'https://www.googleapis.com/auth/drive.file'
]

oauth2_scheme = OAuth2AuthorizationCodeBearer(
    authorizationUrl="https://accounts.google.com/o/oauth2/auth",
    tokenUrl="https://oauth2.googleapis.com/token"
)

class AuthManager:
    def __init__(self):
        self.flow = Flow.from_client_config(
            GOOGLE_CLIENT_CONFIG,
            scopes=SCOPES,
            redirect_uri=GOOGLE_CLIENT_CONFIG["web"]["redirect_uris"][0]
        )
        self._credentials: Optional[Credentials] = None

    def get_authorization_url(self) -> str:
        """Get the Google OAuth2 authorization URL."""
        auth_url, _ = self.flow.authorization_url(
            access_type='offline',
            include_granted_scopes='true'
        )
        return auth_url

    async def handle_callback(self, code: str) -> Credentials:
        """Handle OAuth2 callback and get credentials."""
        self.flow.fetch_token(code=code)
        self._credentials = self.flow.credentials
        return self._credentials

    def get_current_credentials(self) -> Optional[Credentials]:
        """Get current credentials."""
        return self._credentials

auth_manager = AuthManager()

async def get_current_user(token: str = Depends(oauth2_scheme)) -> Credentials:
    """Dependency to get current authenticated user."""
    credentials = auth_manager.get_current_credentials()
    if not credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated"
        )
    return credentials 