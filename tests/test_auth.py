import pytest
import os
from dotenv import load_dotenv
from gsheets_db.auth.authenticator import GoogleAuthenticator, AuthenticationError

# Load environment variables
load_dotenv()

@pytest.fixture
def credentials_path():
    """Fixture to provide credentials path."""
    path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    if not path or not os.path.exists(path):
        pytest.skip("Google credentials not available")
    return path

def test_authenticator_initialization(credentials_path):
    """Test authenticator initialization."""
    auth = GoogleAuthenticator(credentials_path)
    assert auth.creds is None

def test_authentication_process(credentials_path):
    """Test authentication process."""
    auth = GoogleAuthenticator(credentials_path)
    
    # Test authentication
    creds = auth.authenticate()
    assert creds is not None
    assert creds.valid
    
    # Test invalid credentials
    with pytest.raises(AuthenticationError):
        invalid_auth = GoogleAuthenticator("invalid_path")
        invalid_auth.authenticate()