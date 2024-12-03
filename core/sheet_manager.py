from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime
import logging
from .schema import Schema, FieldType
from .connection import SheetConnection
from ..exceptions.custom_exceptions import QuotaExceededError
from ..utils.encryption import Encryptor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SheetManager:
    """Manages CRUD operations for Google Sheets."""
    
    def __init__(self, connection: SheetConnection, schema: Schema, encryption_key: Optional[str] = None):
        self.connection = connection
        self.schema = schema
        self.sheet_id = None
        self.encryptor = Encryptor(encryption_key) if encryption_key else None
        
    async def create_sheet(self, title: str) -> str:
        """
        Create a new sheet with the defined schema.
        
        Args:
            title: Name of the sheet
            
        Returns:
            Sheet ID
        """
        if not self.connection.is_connected():
            await self.connection.connect()
            
        try:
            spreadsheet = {
                'properties': {'title': title},
                'sheets': [{
                    'properties': {'title': self.schema.name},
                    'data': [{
                        'rowData': {
                            'values': self._create_header_row()
                        }
                    }]
                }]
            }
            
            result = self.connection.service.spreadsheets().create(
                body=spreadsheet).execute()
            
            self.sheet_id = result['spreadsheetId']
            logger.info(f"Created new sheet with ID: {self.sheet_id}")
            return self.sheet_id
            
        except Exception as e:
            logger.error(f"Failed to create sheet: {str(e)}")
            raise
            
    async def insert(self, data: Dict[str, Any]) -> None:
        """
        Insert a new row of data.
        
        Args:
            data: Dictionary mapping field names to values
        """
        try:
            validated_data = self._validate_data(data)
            values = self._prepare_row_data(validated_data)
            
            body = {
                'values': [values]
            }
            
            self.connection.service.spreadsheets().values().append(
                spreadsheetId=self.sheet_id,
                range=f"{self.schema.name}!A:A",
                valueInputOption='RAW',
                body=body
            ).execute()
            
            logger.info(f"Inserted new row: {data}")
            
        except Exception as e:
            logger.error(f"Failed to insert data: {str(e)}")
            raise
            
    def _validate_data(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """Validate data against schema."""
        validated = {}
        
        for field in self.schema.fields:
            value = data.get(field.name)
            
            # Validate field
            errors = self.schema.validate_value(field.name, value)
            if errors:
                raise ValueError(f"Validation errors for {field.name}: {', '.join(errors)}")
            
            if value is None:
                if field.required:
                    if field.default is not None:
                        validated[field.name] = field.default
                    else:
                        raise ValueError(f"Required field missing: {field.name}")
            else:
                # Convert and possibly encrypt value
                converted_value = self.schema._convert_value(value, field.field_type)
                if field.encrypted and self.encryptor:
                    validated[field.name] = self.encryptor.encrypt(converted_value)
                else:
                    validated[field.name] = converted_value
                    
        return validated
        
    def _convert_value(self, value: Any, field_type: FieldType) -> Any:
        """Convert value to appropriate type."""
        try:
            if field_type == FieldType.INTEGER:
                return int(value)
            elif field_type == FieldType.FLOAT:
                return float(value)
            elif field_type == FieldType.BOOLEAN:
                return bool(value)
            elif field_type == FieldType.DATE:
                return datetime.strptime(value, "%Y-%m-%d").date()
            elif field_type == FieldType.DATETIME:
                return datetime.fromisoformat(value)
            else:
                return str(value)
        except Exception as e:
            raise ValueError(f"Invalid value for type {field_type}: {value}") 