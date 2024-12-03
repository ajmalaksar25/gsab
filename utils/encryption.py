from typing import Any, Optional
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
import base64
import json
import os
from ..exceptions.custom_exceptions import EncryptionError

class Encryptor:
    """Handles encryption and decryption of sensitive data."""
    
    def __init__(self, key: Optional[str] = None):
        """
        Initialize the encryptor.
        
        Args:
            key: Encryption key (will be generated if not provided)
        """
        self.key = key or self._generate_key()
        self.fernet = Fernet(self.key.encode() if isinstance(self.key, str) else self.key)
        
    @staticmethod
    def _generate_key() -> str:
        """Generate a new encryption key."""
        return base64.urlsafe_b64encode(os.urandom(32)).decode()
        
    def encrypt(self, data: Any) -> str:
        """
        Encrypt data.
        
        Args:
            data: Data to encrypt
            
        Returns:
            Encrypted string
        """
        try:
            # Convert data to JSON string
            json_data = json.dumps(data)
            # Encrypt and return as base64 string
            encrypted = self.fernet.encrypt(json_data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt data: {str(e)}")
            
    def decrypt(self, encrypted_data: str) -> Any:
        """
        Decrypt data.
        
        Args:
            encrypted_data: Encrypted string
            
        Returns:
            Decrypted data
        """
        try:
            # Decode base64 string
            decoded = base64.urlsafe_b64decode(encrypted_data.encode())
            # Decrypt data
            decrypted = self.fernet.decrypt(decoded)
            # Parse JSON string
            return json.loads(decrypted.decode())
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt data: {str(e)}") 