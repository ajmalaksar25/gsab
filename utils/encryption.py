from typing import Any, Optional
from cryptography.fernet import Fernet
import base64
import json
from ..exceptions.custom_exceptions import EncryptionError

class Encryptor:
    """Handles encryption and decryption of sensitive data."""
    
    def __init__(self, key: Optional[str] = None):
        """
        Initialize the encryptor.
        
        Args:
            key: Encryption key (will be generated if not provided)
        """
        try:
            if key:
                # Convert the key to a valid Fernet key
                # Fernet requires a 32-byte key that is base64-encoded
                key_bytes = key.encode() if isinstance(key, str) else key
                if len(key_bytes) < 32:
                    # Pad the key if it's too short
                    key_bytes = key_bytes.ljust(32, b'\0')
                elif len(key_bytes) > 32:
                    # Truncate if too long
                    key_bytes = key_bytes[:32]
                
                # Create a valid Fernet key by base64 encoding the 32-byte key
                self.key = base64.urlsafe_b64encode(key_bytes)
            else:
                self.key = Fernet.generate_key()
                
            self.fernet = Fernet(self.key)
            
        except Exception as e:
            raise EncryptionError(f"Invalid encryption key format: {str(e)}")

    def _pad_base64(self, key: str) -> str:
        """Add padding to base64 string if needed."""
        padding = len(key) % 4
        if padding:
            return key + '=' * (4 - padding)
        return key
            
    def encrypt(self, data: Any) -> str:
        """Encrypt data."""
        try:
            json_data = json.dumps(data)
            encrypted = self.fernet.encrypt(json_data.encode())
            return base64.urlsafe_b64encode(encrypted).decode()
        except Exception as e:
            raise EncryptionError(f"Failed to encrypt data: {str(e)}")
            
    def decrypt(self, encrypted_data: str) -> Any:
        """Decrypt data."""
        try:
            padded_data = self._pad_base64(encrypted_data)
            decoded = base64.urlsafe_b64decode(padded_data.encode())
            decrypted = self.fernet.decrypt(decoded)
            return json.loads(decrypted.decode())
        except Exception as e:
            raise EncryptionError(f"Failed to decrypt data: {str(e)}") 