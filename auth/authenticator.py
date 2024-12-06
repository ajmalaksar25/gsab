from google.oauth2 import service_account
from google.auth.transport.requests import Request

class GoogleAuthenticator:
    """Handles authentication with Google Sheets API."""
    
    SCOPES = [
        'https://www.googleapis.com/auth/spreadsheets',
        'https://www.googleapis.com/auth/drive.file',
        'https://www.googleapis.com/auth/drive'
    ]
    
    def __init__(self, credentials_path: str):
        self.credentials_path = credentials_path
        self.creds = None

    def authenticate(self):
        """
        Authenticate using service account credentials.
        
        Returns:
            Google OAuth2 credentials
        """
        try:
            self.creds = service_account.Credentials.from_service_account_file(
                self.credentials_path,
                scopes=self.SCOPES
            )
            # Ensure the credentials are valid
            if not self.creds.valid:
                request = Request()
                self.creds.refresh(request)
            return self.creds
        except Exception as e:
            raise AuthenticationError(f"Authentication failed: {str(e)}")

class AuthenticationError(Exception):
    """Custom exception for authentication errors."""
    pass