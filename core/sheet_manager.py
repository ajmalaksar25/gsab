from typing import List, Dict, Any, Optional
import asyncio
from datetime import datetime
import logging
from .schema import Schema, FieldType
from .connection import SheetConnection
from ..exceptions.custom_exceptions import QuotaExceededError
from ..utils.encryption import Encryptor
from googleapiclient.discovery import build

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

    def _create_header_row(self) -> List[Dict]:
        """
        Create header row based on schema fields.
        
        Returns:
            List of cell values for the header row
        """
        return [{
            'userEnteredValue': {'stringValue': field.name},
            'userEnteredFormat': {
                'backgroundColor': {'red': 0.9, 'green': 0.9, 'blue': 0.9},
                'textFormat': {'bold': True},
                'horizontalAlignment': 'CENTER'
            }
        } for field in self.schema.fields]

    def _prepare_row_data(self, data: Dict[str, Any]) -> List[Any]:
        """
        Prepare row data for insertion.
        
        Args:
            data: Dictionary of validated data
            
        Returns:
            List of values in the order defined by schema
        """
        row_data = []
        for field in self.schema.fields:
            value = data.get(field.name)
            
            # Handle None values
            if value is None:
                row_data.append('')
                continue
            
            # Convert to string representation for sheets
            if field.field_type == FieldType.DATE:
                value = value.isoformat()
            elif field.field_type == FieldType.DATETIME:
                value = value.isoformat()
            elif field.field_type == FieldType.BOOLEAN:
                value = str(value).upper()
            else:
                value = str(value)
            
            row_data.append(value)
        
        return row_data

    async def read(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """
        Read data from sheet, optionally filtered.
        
        Args:
            filters: Dictionary of field-value pairs to filter by
        
        Returns:
            List of row data as dictionaries
        """
        try:
            range_name = f"{self.schema.name}!A1:Z"
            result = self.connection.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=range_name
            ).execute()
            
            rows = result.get('values', [])
            if not rows:
                return []
            
            # First row is headers
            headers = rows[0]
            data = []
            
            for row in rows[1:]:
                # Pad row with empty strings if needed
                row_data = row + [''] * (len(headers) - len(row))
                row_dict = dict(zip(headers, row_data))
                
                # Apply filters if any
                if filters:
                    if all(row_dict.get(k) == str(v) for k, v in filters.items()):
                        data.append(row_dict)
                else:
                    data.append(row_dict)
                    
            return data
            
        except Exception as e:
            logger.error(f"Failed to read data: {str(e)}")
            raise

    async def update(self, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """
        Update rows matching filters with new values.
        
        Args:
            filters: Dictionary of field-value pairs to filter by
            updates: Dictionary of field-value pairs to update
        
        Returns:
            Number of rows updated
        """
        try:
            # Read existing data
            rows = await self.read(filters)
            if not rows:
                return 0
            
            # Get all data to find row indices
            all_rows = await self.read()
            updated_count = 0
            
            for row in rows:
                row_index = all_rows.index(row) + 2  # +2 for 1-based index and header row
                
                # Prepare update data
                validated_updates = self._validate_data({**row, **updates})
                update_values = self._prepare_row_data(validated_updates)
                
                # Update row
                range_name = f"{self.schema.name}!A{row_index}"
                body = {
                    'values': [update_values]
                }
                
                self.connection.service.spreadsheets().values().update(
                    spreadsheetId=self.sheet_id,
                    range=range_name,
                    valueInputOption='RAW',
                    body=body
                ).execute()
                
                updated_count += 1
                
            return updated_count
            
        except Exception as e:
            logger.error(f"Failed to update data: {str(e)}")
            raise

    async def delete(self, filters: Dict[str, Any]) -> int:
        """
        Delete rows matching filters.
        
        Args:
            filters: Dictionary of field-value pairs to filter by
        
        Returns:
            Number of rows deleted
        """
        try:
            # Read existing data
            rows = await self.read(filters)
            if not rows:
                return 0
            
            # Get all data to find row indices
            all_rows = await self.read()
            deleted_count = 0
            
            # Get the actual sheet ID
            spreadsheet = self.connection.service.spreadsheets().get(
                spreadsheetId=self.sheet_id
            ).execute()
            
            # Find the sheet with matching title
            sheet_id = None
            for sheet in spreadsheet['sheets']:
                if sheet['properties']['title'] == self.schema.name:
                    sheet_id = sheet['properties']['sheetId']
                    break
                
            if sheet_id is None:
                raise ValueError(f"Sheet with name {self.schema.name} not found")
            
            # Sort indices in descending order to avoid shifting issues
            indices = sorted([all_rows.index(row) + 2 for row in rows], reverse=True)
            
            for row_index in indices:
                # Delete row
                request = {
                    'deleteDimension': {
                        'range': {
                            'sheetId': sheet_id,  # Use the actual sheet ID
                            'dimension': 'ROWS',
                            'startIndex': row_index - 1,
                            'endIndex': row_index
                        }
                    }
                }
                
                self.connection.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheet_id,
                    body={'requests': [request]}
                ).execute()
                
                deleted_count += 1
                
            return deleted_count
            
        except Exception as e:
            logger.error(f"Failed to delete data: {str(e)}")
            raise

    async def rename_sheet(self, new_title: str) -> None:
        """
        Rename the sheet.
        
        Args:
            new_title: New title for the sheet
        """
        try:
            request = {
                'updateSpreadsheetProperties': {
                    'properties': {'title': new_title},
                    'fields': 'title'
                }
            }
            
            self.connection.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id,
                body={'requests': [request]}
            ).execute()
            
            logger.info(f"Renamed sheet to: {new_title}")
            
        except Exception as e:
            logger.error(f"Failed to rename sheet: {str(e)}")
            raise

    async def delete_sheet(self) -> None:
        """Delete the entire spreadsheet using Drive API."""
        try:
            # First try using Drive API
            try:
                # Build the Drive API service
                drive_service = build('drive', 'v3', credentials=self.connection.credentials)
                
                # Delete the file using Drive API
                drive_service.files().delete(
                    fileId=self.sheet_id,
                    supportsAllDrives=True
                ).execute()
                
                logger.info(f"Deleted spreadsheet: {self.sheet_id}")
                self.sheet_id = None
                return
                
            except Exception as drive_error:
                if 'accessNotConfigured' in str(drive_error):
                    logger.warning("Drive API not enabled. Falling back to content clearing...")
                else:
                    raise drive_error
                
            # Fallback: Clear all content if Drive API fails
            range_name = f"{self.schema.name}!A2:Z"
            self.connection.service.spreadsheets().values().clear(
                spreadsheetId=self.sheet_id,
                range=range_name
            ).execute()
            
            logger.info(f"Cleared sheet contents: {self.sheet_id}")
            self.sheet_id = None
            
        except Exception as e:
            logger.error(f"Failed to delete sheet: {str(e)}")
            raise