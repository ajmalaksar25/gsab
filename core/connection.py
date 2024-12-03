from typing import Optional, Dict, Any
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from ..auth.authenticator import GoogleAuthenticator
from ..exceptions.custom_exceptions import ConnectionError

class SheetConnection:
    """Manages connection to Google Sheets API."""
    
    def __init__(self, credentials_path: Optional[str] = None, credentials: Optional[Credentials] = None):
        """
        Initialize connection with either credentials path or credentials object.
        
        Args:
            credentials_path: Path to credentials JSON file
            credentials: Google OAuth2 credentials object
        """
        if credentials_path:
            self.authenticator = GoogleAuthenticator(credentials_path)
            self.credentials = None
        elif credentials:
            self.credentials = credentials
            self.authenticator = None
        else:
            raise ValueError("Either credentials_path or credentials must be provided")
        self.service = None
        
    async def connect(self) -> None:
        """Establish connection to Google Sheets API."""
        try:
            if self.authenticator:
                self.credentials = self.authenticator.authenticate()
            self.service = build('sheets', 'v4', credentials=self.credentials)
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Google Sheets API: {str(e)}")
            
    def is_connected(self) -> bool:
        """Check if connection is established."""
        return self.service is not None 