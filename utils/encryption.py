from typing import Any
import base64
import json
from cryptography.fernet import Fernet
from ..exceptions.custom_exceptions import EncryptionError

class Encryptor:
    """Handles encryption and decryption of data."""
    
    def __init__(self, key: str):
        """Initialize encryptor with key."""
        try:
            self.fernet = Fernet(key.encode() if isinstance(key, str) else key)
        except Exception as e:
            raise EncryptionError(f"Failed to initialize encryptor: {str(e)}")

    def encrypt(self, data: Any) -> str:
        """Encrypt data."""
        try:
            if data is None:
                raise ValueError("Cannot encrypt None value")
                
            # Convert data to JSON string
            json_data = json.dumps(data)
            encrypted_data = self.fernet.encrypt(json_data.encode())
            return encrypted_data.decode()
        except Exception as e:
            raise EncryptionError(f"Encryption failed: {str(e)}")

    def decrypt(self, encrypted_data: str) -> Any:
        """Decrypt data."""
        try:
            if not encrypted_data:
                return ""
                
            decrypted = self.fernet.decrypt(encrypted_data.encode())
            return json.loads(decrypted.decode())
        except Exception as e:
            raise EncryptionError(f"Decryption failed: {str(e)}") 