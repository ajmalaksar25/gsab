import logging
import re
from typing import Any, Dict, List, Optional

from googleapiclient.discovery import build

from ..utils.encryption import Encryptor
from .connection import SheetConnection
from .schema import Schema

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def _match_op(actual: Any, op: str, target: Any) -> bool:
    """Evaluate a single filter operator against a record value."""
    try:
        if op == "$eq":
            return actual == target
        if op == "$ne":
            return actual != target
        if op == "$gt":
            return actual is not None and actual > target
        if op == "$gte":
            return actual is not None and actual >= target
        if op == "$lt":
            return actual is not None and actual < target
        if op == "$lte":
            return actual is not None and actual <= target
        if op == "$in":
            return actual in target
        if op == "$nin":
            return actual not in target
        if op == "$contains":
            return str(target) in str(actual)
        if op == "$regex":
            return re.search(target, str(actual)) is not None
    except TypeError:
        return False
    raise ValueError(f"Unknown filter operator: {op}")


class SheetManager:
    """Manages CRUD operations for Google Sheets."""

    def __init__(
        self, connection: SheetConnection, schema: Schema, encryption_key: Optional[str] = None
    ):
        """Initialize sheet manager."""
        self.connection = connection
        self.schema = schema
        self.sheet_id = None
        self._field_map = {field.name: field for field in self.schema.fields}

        # Initialize encryptor only if we have encrypted fields
        has_encrypted_fields = any(field.encrypted for field in self.schema.fields)
        self.encryptor = (
            Encryptor(encryption_key) if has_encrypted_fields and encryption_key else None
        )

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
                "properties": {"title": title},
                "sheets": [
                    {
                        "properties": {"title": self.schema.name},
                        "data": [{"rowData": {"values": self._create_header_row()}}],
                    }
                ],
            }

            result = self.connection.service.spreadsheets().create(body=spreadsheet).execute()

            self.sheet_id = result["spreadsheetId"]
            logger.info(f"Created new sheet with ID: {self.sheet_id}")
            return self.sheet_id

        except Exception as e:
            logger.error(f"Failed to create sheet: {str(e)}")
            raise

    def _encode_row(self, data: Dict[str, Any]) -> List[str]:
        """Validate one record and return its cell values (encrypting flagged fields once)."""
        errors = self.schema.validate(data)
        if errors:
            raise ValueError(f"Validation errors: {', '.join(errors)}")
        row = []
        for field in self.schema.fields:
            value = data.get(field.name)
            if value is None:
                value = field.default
            if value is None or value == "":
                row.append("")
                continue
            value = self.schema._convert_value(value, field.field_type)
            if field.encrypted and self.encryptor:
                value = self.encryptor.encrypt(value)
            row.append(str(value))
        return row

    async def insert(self, data: Dict[str, Any]) -> None:
        """Insert a single record."""
        await self.bulk_insert([data])

    async def bulk_insert(self, records: List[Dict[str, Any]]) -> int:
        """Insert many records in a single append call. Returns the number inserted."""
        if not self.sheet_id:
            raise ValueError("Sheet not created")
        rows = [self._encode_row(r) for r in records]
        if not rows:
            return 0
        self.connection.service.spreadsheets().values().append(
            spreadsheetId=self.sheet_id,
            range=f"{self.schema.name}!A:A",
            valueInputOption="RAW",
            body={"values": rows},
        ).execute()
        logger.info("Inserted %d row(s)", len(rows))
        return len(rows)

    async def from_dataframe(self, df) -> int:
        """Insert every row of a pandas DataFrame in bulk. Returns the number inserted."""
        return await self.bulk_insert(df.to_dict("records"))

    async def to_dataframe(self, filters: Optional[Dict[str, Any]] = None):
        """Read records into a pandas DataFrame (install the `pandas` extra)."""
        import pandas as pd

        return pd.DataFrame(await self.read(filters))

    def _create_header_row(self) -> List[Dict]:
        """
        Create header row based on schema fields.

        Returns:
            List of cell values for the header row
        """
        return [
            {
                "userEnteredValue": {"stringValue": field.name},
                "userEnteredFormat": {
                    "backgroundColor": {"red": 0.9, "green": 0.9, "blue": 0.9},
                    "textFormat": {"bold": True},
                    "horizontalAlignment": "CENTER",
                },
            }
            for field in self.schema.fields
        ]

    async def read(self, filters: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Read records matching the filters."""
        try:
            # Get all data
            result = (
                self.connection.service.spreadsheets()
                .values()
                .get(spreadsheetId=self.sheet_id, range=f"{self.schema.name}!A:Z")
                .execute()
            )

            if "values" not in result:
                return []

            values = result["values"]
            if len(values) <= 1:  # Only header row
                return []

            # Get header row
            headers = values[0]

            # Process data rows
            records = []
            for row_index, row in enumerate(values[1:], start=1):
                record = {}

                # Pad row with empty strings if necessary
                row_data = row + [""] * (len(headers) - len(row))

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
                record["_row_index"] = row_index

                # Apply filters
                if filters and not self._matches_filters(record, filters):
                    continue

                records.append(record)

            return records

        except Exception as e:
            logger.error(f"Failed to read data: {str(e)}")
            raise

    def _matches_filters(self, record: Dict[str, Any], filters: Dict[str, Any]) -> bool:
        """Check whether a record matches all filters (equality or operator dicts).

        Operators: $eq $ne $gt $gte $lt $lte $in $nin $contains $regex.
        """
        for field, cond in filters.items():
            actual = record.get(field)
            if isinstance(cond, dict):
                if not all(_match_op(actual, op, target) for op, target in cond.items()):
                    return False
            elif actual != cond:
                return False
        return True

    def column(self, field_name: str) -> str:
        """Return the spreadsheet column letter (A, B, …) for a schema field."""
        names = [f.name for f in self.schema.fields]
        if field_name not in names:
            raise ValueError(f"Unknown field: {field_name}")
        return chr(ord("A") + names.index(field_name))

    async def query(self, sql: str) -> List[Dict[str, Any]]:
        """Run a Google Visualization (gviz) query against this tab, server-side.

        Columns are referenced by letter — use ``column()`` to map a field name.
        Example::

            await db.query("SELECT A, D WHERE D = 'pro' ORDER BY A DESC LIMIT 10")

        Returns a list of dicts keyed by the sheet's header labels. Filtering,
        sorting and aggregation run on Google's servers, not in Python.
        """
        if not self.sheet_id:
            raise ValueError("Sheet not created")
        if not self.connection.is_connected():
            await self.connection.connect()
        from .query import run_gviz_query

        return run_gviz_query(
            self.connection.credentials, self.sheet_id, sql, sheet=self.schema.name
        )

    async def update(self, filters: Dict[str, Any], updates: Dict[str, Any]) -> int:
        """Update records matching the filters."""
        try:
            # First get all matching records
            matching_records = await self.read(filters)
            if not matching_records:
                logger.info("No rows found matching the filters")
                return 0

            # Get the sheet ID and range
            sheet_metadata = (
                self.connection.service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
            )
            sheet_id = sheet_metadata["sheets"][0]["properties"]["sheetId"]

            # Prepare batch update request
            requests = []
            for record in matching_records:
                row_index = record.get("_row_index", 0)  # We need to store row index during read

                values = []
                for field in self.schema.fields:
                    if field.name in updates:
                        value = updates[field.name]
                        if field.encrypted and self.encryptor:
                            value = self.encryptor.encrypt(value)
                        values.append(value)
                    else:
                        values.append(record[field.name])

                requests.append(
                    {
                        "updateCells": {
                            "range": {
                                "sheetId": sheet_id,
                                "startRowIndex": row_index,
                                "endRowIndex": row_index + 1,
                                "startColumnIndex": 0,
                                "endColumnIndex": len(self.schema.fields),
                            },
                            "rows": [
                                {
                                    "values": [
                                        {"userEnteredValue": {"stringValue": str(v)}}
                                        for v in values
                                    ]
                                }
                            ],
                            "fields": "userEnteredValue",
                        }
                    }
                )

            if requests:
                self.connection.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheet_id, body={"requests": requests}
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
            spreadsheet = (
                self.connection.service.spreadsheets().get(spreadsheetId=self.sheet_id).execute()
            )

            # Find the sheet with matching title
            sheet_id = None
            for sheet in spreadsheet["sheets"]:
                if sheet["properties"]["title"] == self.schema.name:
                    sheet_id = sheet["properties"]["sheetId"]
                    break

            if sheet_id is None:
                raise ValueError(f"Sheet with name {self.schema.name} not found")

            # Sort indices in descending order to avoid shifting issues
            indices = sorted([all_rows.index(row) + 2 for row in rows], reverse=True)

            for row_index in indices:
                # Delete row
                request = {
                    "deleteDimension": {
                        "range": {
                            "sheetId": sheet_id,  # Use the actual sheet ID
                            "dimension": "ROWS",
                            "startIndex": row_index - 1,
                            "endIndex": row_index,
                        }
                    }
                }

                self.connection.service.spreadsheets().batchUpdate(
                    spreadsheetId=self.sheet_id, body={"requests": [request]}
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
                "updateSpreadsheetProperties": {
                    "properties": {"title": new_title},
                    "fields": "title",
                }
            }

            self.connection.service.spreadsheets().batchUpdate(
                spreadsheetId=self.sheet_id, body={"requests": [request]}
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
                drive_service = build("drive", "v3", credentials=self.connection.credentials)

                # Delete the file using Drive API
                drive_service.files().delete(fileId=self.sheet_id, supportsAllDrives=True).execute()

                logger.info(f"Deleted spreadsheet: {self.sheet_id}")
                self.sheet_id = None
                return

            except Exception as drive_error:
                if "accessNotConfigured" in str(drive_error):
                    logger.warning("Drive API not enabled. Falling back to content clearing...")
                else:
                    raise drive_error

            # Fallback: Clear all content if Drive API fails
            range_name = f"{self.schema.name}!A2:Z"
            self.connection.service.spreadsheets().values().clear(
                spreadsheetId=self.sheet_id, range=range_name
            ).execute()

            logger.info(f"Cleared sheet contents: {self.sheet_id}")
            self.sheet_id = None

        except Exception as e:
            logger.error(f"Failed to delete sheet: {str(e)}")
            raise
