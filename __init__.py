"""Google Sheets as Database package."""

__version__ = "0.1.0"

from .core.sheet_manager import SheetManager
from .core.schema import Schema, Field, FieldType
from .core.connection import SheetConnection

__all__ = ['SheetConnection', 'Schema', 'Field', 'FieldType', 'SheetManager']