from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
import os.path
import pickle

class GoogleAuthenticator:
    """Handles authentication with Google Sheets API."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_path: str, token_path: str = 'token.pickle'):
        """
        Initialize the authenticator.
        
        Args:
            credentials_path: Path to the credentials.json file
            token_path: Path to save/load the token pickle file
        """
        self.credentials_path = credentials_path
        self.token_path = token_path
        self.creds = None

    def authenticate(self) -> Credentials:
        """
        Authenticate with Google Sheets API.
        
        Returns:
            Google OAuth2 credentials
        """
        if os.path.exists(self.token_path):
            with open(self.token_path, 'rb') as token:
                self.creds = pickle.load(token)

        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    self.credentials_path, self.SCOPES)
                self.creds = flow.run_local_server(port=0)

            with open(self.token_path, 'wb') as token:
                pickle.dump(self.creds, token)

        return self.creds 