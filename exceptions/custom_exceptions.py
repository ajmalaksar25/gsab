class GSheetsDBException(Exception):
    """Base exception for GSheetsDB library."""
    pass

class ConnectionError(GSheetsDBException):
    """Raised when connection to Google Sheets API fails."""
    pass

class QuotaExceededError(GSheetsDBException):
    """Raised when Google Sheets API quota is exceeded."""
    pass

class EncryptionError(GSheetsDBException):
    """Raised when encryption/decryption operations fail."""
    pass 