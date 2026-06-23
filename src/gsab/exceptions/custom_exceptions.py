class GSheetsDBException(Exception):
    """Base exception for the GSAB library."""

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


class AuthError(GSheetsDBException):
    """Raised when authentication or credential resolution fails."""

    pass


# Friendly alias for the package base exception.
GSABError = GSheetsDBException
