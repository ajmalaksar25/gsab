import pytest
import os
from dotenv import load_dotenv
from gsheets_db.core.connection import SheetConnection
from gsheets_db.core.schema import Schema, Field, FieldType
from gsheets_db.core.sheet_manager import SheetManager

# Load environment variables
load_dotenv()

@pytest.fixture
async def sheet_manager():
    """Fixture to create and cleanup sheet manager."""
    # Create schema
    schema = Schema("test_users", [
        Field("id", FieldType.INTEGER, required=True, unique=True),
        Field("email", FieldType.STRING, required=True),
        Field("password", FieldType.STRING, required=True, encrypted=True)
    ])

    # Connect to Google Sheets
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    connection = SheetConnection(credentials_path=credentials_path)
    await connection.connect()

    # Create sheet manager
    manager = SheetManager(
        connection, 
        schema, 
        encryption_key=os.getenv("ENCRYPTION_KEY")
    )
    
    yield manager
    
    # Cleanup
    if manager.sheet_id:
        try:
            await manager.delete_sheet()
        except Exception:
            pass

@pytest.mark.asyncio
async def test_create_sheet(sheet_manager):
    sheet_id = await sheet_manager.create_sheet("Test Users Database")
    assert sheet_id is not None
    assert isinstance(sheet_id, str)

@pytest.mark.asyncio
async def test_crud_operations(sheet_manager):
    # Create sheet
    await sheet_manager.create_sheet("Test Users Database")
    
    # Test Insert
    test_data = {
        "id": 1,
        "email": "test@example.com",
        "password": "secretpass123"
    }
    await sheet_manager.insert(test_data)
    
    # Test Read
    rows = await sheet_manager.read({"id": 1})
    assert rows
    assert rows[0]["email"] == "test@example.com"
    
    # Test Update
    updated = await sheet_manager.update(
        {"id": 1}, 
        {"email": "updated@example.com"}
    )
    assert updated == 1
    
    # Verify Update
    rows = await sheet_manager.read({"id": 1})
    assert rows[0]["email"] == "updated@example.com"
    
    # Test Delete
    deleted = await sheet_manager.delete({"id": 1})
    assert deleted == 1
    
    # Verify Deletion
    rows = await sheet_manager.read({"id": 1})
    assert not rows

@pytest.mark.asyncio
async def test_rename_sheet(sheet_manager):
    await sheet_manager.create_sheet("Test Users Database")
    await sheet_manager.rename_sheet("Updated Test Users Database")
    
    # Verify rename (would need to implement a method to get sheet name)
    assert True  # For now, just verify no exceptions

@pytest.mark.asyncio
async def test_validation(sheet_manager):
    await sheet_manager.create_sheet("Test Users Database")
    
    # Test required field validation
    with pytest.raises(ValueError):
        await sheet_manager.insert({"id": 1})  # Missing required fields
    
    # Test unique constraint
    await sheet_manager.insert({
        "id": 1,
        "email": "test@example.com",
        "password": "pass123"
    })
    
    with pytest.raises(ValueError):
        await sheet_manager.insert({
            "id": 1,  # Duplicate ID
            "email": "other@example.com",
            "password": "pass456"
        }) 