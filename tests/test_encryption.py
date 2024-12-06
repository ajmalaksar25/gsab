import pytest
from dotenv import load_dotenv
import os
from cryptography.fernet import Fernet

# Load environment variables
load_dotenv()

@pytest.fixture
def encryption_key():
    """Fixture to provide encryption key."""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        key = Fernet.generate_key().decode()
    return key

def test_encryption_edge_cases(encryption_key):
    """Test encryption edge cases."""
    from gsheets_db.utils.encryption import Encryptor
    
    encryptor = Encryptor(encryption_key)
    
    # Test empty string
    encrypted = encryptor.encrypt("")
    decrypted = encryptor.decrypt(encrypted)
    assert decrypted == ""
    
    # Test large data
    large_data = "x" * 1000000
    encrypted = encryptor.encrypt(large_data)
    decrypted = encryptor.decrypt(encrypted)
    assert decrypted == large_data
    
    # Test special characters
    special = "!@#$%^&*()\n\t"
    encrypted = encryptor.encrypt(special)
    decrypted = encryptor.decrypt(encrypted)
    assert decrypted == special 