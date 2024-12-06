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
        """Initialize sheet manager."""
        self.connection = connection
        self.schema = schema
        self.sheet_id = None
        self._field_map = {field.name: field for field in self.schema.fields}
        
        # Initialize encryptor only if we have encrypted fields
        has_encrypted_fields = any(field.encrypted for field in self.schema.fields)
        self.encryptor = Encryptor(encryption_key) if has_encrypted_fields and encryption_key else None
        
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
            values = []
            
            # Prepare row data with encryption
            for field in self.schema.fields:
                value = validated_data.get(field.name, '')
                
                # Handle encryption for fields marked as encrypted
                if field.encrypted and self.encryptor and value:
                    try:
                        value = self.encryptor.encrypt(value)
                        logger.info(f"Encrypted field {field.name}")
                    except Exception as e:
                        logger.error(f"Failed to encrypt field {field.name}: {str(e)}")
                        raise
                
                values.append(str(value))
            
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
        """Read records matching the filters."""
        try:
            # Get all data
            result = self.connection.service.spreadsheets().values().get(
                spreadsheetId=self.sheet_id,
                range=f"{self.schema.name}!A:Z"
            ).execute()

            if 'values' not in result:
                return []

            values = result['values']
            if len(values) <= 1:  # Only header row
                return []

            # Get header row
            headers = values[0]
            
            # Process data rows
            records = []
            for row_index, row in enumerate(values[1:], start=1):
                record = {}
                
                # Pad row with empty strings if necessary
                row_data = row + [''] * (len(headers) - len(row))
                
                for header, value in zip(headers, row_data):
                    field = self._field_map.get(header)
                    if field:
                        # Handle encrypted fields
                        if field.encrypted and self.encryptor and value:
                            try:
                                value = self.encryptor.decrypt(value)
                            except Exception as e:
                                logger.warning(f"Failed to decrypt field {header}: {str(e)}")
                                
                        # Convert value to appropriate type
                        try:
                            record[header] = self.schema._convert_value(value, field.field_type)
                        except ValueError:
                            # If conversion fails, store as string
                            record[header] = str(value)
                
                # Store row index for update operations
                record['_row_index'] = row_index
                
                # Apply filters
                if filters and not self._matches_filters(record, filters):
                    continue
                    
                records.append(record)

            return records

        except Exception as e:
            logger.error(f"Failed to read data: {str(e)}")
            raise

    def _matches_filters(self, record: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check if record matches all filters."""
        for field, filter_value in filters.items():
            if field not in record:
                return False
                
            if isinstance(filter_value, dict):
                # Handle operators like $regex
                for op, value in filter_value.items():
                    if op == '$regex':
                        import re
                        if not re.search(value, str(record[field])):
                            return False
            else:
                # Direct value comparison
                if record[field] != filter_value:
                    return False
                    
        return True

    async def update(self, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """Update records matching the filters."""
        try:
            # First get all matching records
            matching_records = await self.read(filters)
            if not matching_records:
                logger.info("No rows found matching the filters")
                return 0

            # Get the sheet ID and range
            sheet_metadata = self.connection.service.spreadsheets().get(
                spreadsheetId=self.sheet_id
            ).execute()
            sheet_id = sheet_metadata['sheets'][0]['properties']['sheetId']

            # Prepare batch update request
            requests = []
            for record in matching_records:
                row_index = record.get('_row_index', 0)  # We need to store row index during read
                
                values = []
                for field in self.schema.fields:
                    if field.name in updates:
                        value = updates[field.name]
                        if field.encrypted and self.encryptor:
                            value = self.encryptor.encrypt(value)
                        values.append(value)
                    else:
                        values.append(record[field.name])

                requests.append({
                    'updateCells': {
                        'range': {
                            'sheetId': sheet_id,
                            'startRowIndex': row_index,
                            'endRowIndex': row_index + 1,
                            'startColumnIndex': 0,
                            'endColumnIndex': len(self.schema.fields)
                        },
                        'rows': [{'values': [{'userEnteredValue': {'stringValue': str(v)}} for v in values]}],
                        'fields': 'userEnteredValue'
                    }
                })

            if requests:
                self.connection.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheet_id,
                    body={'requests': requests}
                ).execute()

            return len(matching_records)

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