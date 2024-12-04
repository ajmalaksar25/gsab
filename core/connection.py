from typing import Optional, Dict, Any
from google.oauth2 import service_account
from googleapiclient.discovery import build
from ..auth.authenticator import GoogleAuthenticator
from ..exceptions.custom_exceptions import ConnectionError

class SheetConnection:
    """Manages connection to Google Sheets API."""
    
    def __init__(self, credentials_path: str = None):
        """Initialize connection with credentials path."""
        self.credentials_path = credentials_path
        self.credentials = None
        self.service = None
        
    async def connect(self) -> None:
        """Establish connection to Google Sheets API."""
        try:
            SCOPES = ['https://www.googleapis.com/auth/spreadsheets']
            
            # Use service account credentials
            self.credentials = service_account.Credentials.from_service_account_file(
                self.credentials_path, 
                scopes=SCOPES
            )
            
            self.service = build('sheets', 'v4', credentials=self.credentials)
            
        except Exception as e:
            raise ConnectionError(f"Failed to connect to Google Sheets API: {str(e)}")

            
    def is_connected(self) -> bool:
        """Check if connection is established."""
        return self.service is not None 