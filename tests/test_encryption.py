import pytest
from dotenv import load_dotenv
import os
from cryptography.fernet import Fernet
from gsab.utils.encryption import EncryptionError

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
    from gsab.utils.encryption import Encryptor
    
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

@pytest.mark.parametrize("test_input", [
    "",  # Empty string
    "Hello World",  # Simple string
    "!@#$%^&*()",  # Special characters
    "🌟💫✨",  # Unicode/Emoji
    "A" * 1000,  # Long string
])

def test_encryption_various_inputs(encryption_key, test_input):
    """Test encryption with various input types."""
    from gsab.utils.encryption import Encryptor

    encryptor = Encryptor(encryption_key)
    encrypted = encryptor.encrypt(test_input)
    decrypted = encryptor.decrypt(encrypted)
    assert decrypted == test_input

def test_encryption_errors(encryption_key):
    """Test encryption error handling."""
    from gsab.utils.encryption import Encryptor
    encryptor = Encryptor(encryption_key)
    
    # Test invalid encrypted data
    with pytest.raises(EncryptionError):
        encryptor.decrypt("invalid_data")
    
    # Test None input - should raise EncryptionError due to try-except wrapper
    with pytest.raises(EncryptionError):
        encryptor.encrypt(None)
    
    # Test invalid data format
    with pytest.raises(EncryptionError):
        encryptor.decrypt("not-base64-encoded==") 