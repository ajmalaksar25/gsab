import pytest
import os
from pathlib import Path
from dotenv import load_dotenv
from cryptography.fernet import Fernet
from gsab.core.connection import SheetConnection
from gsab.core.schema import Schema, Field, FieldType
from gsab.core.sheet_manager import SheetManager

# Load environment variables
load_dotenv()

class TestSetup:
    """Test setup and utilities."""
    
    @staticmethod
    def get_test_schema(encrypted_fields=None):
        """Get test schema with optional encrypted fields."""
        encrypted_fields = encrypted_fields or []
        return Schema("test_data", [
            Field("id", FieldType.INTEGER, required=True, unique=True),
            Field("name", FieldType.STRING, required=True),
            Field("email", FieldType.STRING, required=True, pattern=r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$"),
            Field("age", FieldType.INTEGER, required=True, min_value=0, max_value=150),
            Field("salary", FieldType.FLOAT, required=True),
            Field("is_active", FieldType.BOOLEAN, required=True),
            Field("notes", FieldType.STRING, required=True, encrypted="notes" in encrypted_fields)
        ])

    @staticmethod
    def get_test_data(count=1):
        """Generate test data records."""
        base_data = {
            "name": "Test User",
            "email": "test@example.com",
            "age": 30,
            "salary": 50000.00,
            "is_active": True,
            "notes": "Test notes"
        }
        
        if count == 1:
            base_data["id"] = 1
            return base_data
        
        return [
            {**base_data, 
             "id": i + 1,
             "name": f"Test User {i + 1}",
             "email": f"test{i + 1}@example.com",
             "notes": f"Test notes {i + 1}"
            } for i in range(count)
        ]

@pytest.fixture
def encryption_key():
    """Fixture to provide encryption key."""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        key = Fernet.generate_key().decode()
    return key

@pytest.fixture
async def sheet_manager(encryption_key):
    """Fixture to create and cleanup sheet manager."""
    credentials_path = os.getenv("GOOGLE_CREDENTIALS_PATH")
    if not credentials_path:
        pytest.skip("GOOGLE_CREDENTIALS_PATH environment variable not set")
    
    if not os.path.exists(credentials_path):
        pytest.skip(f"Credentials file not found at {credentials_path}")
        
    # Verify credentials content
    try:
        with open(credentials_path, 'r') as f:
            import json
            creds = json.load(f)
            required_fields = ['token_uri', 'client_email', 'private_key']
            missing = [f for f in required_fields if f not in creds]
            if missing:
                pytest.skip(f"Credentials missing required fields: {', '.join(missing)}")
    except Exception as e:
        pytest.skip(f"Failed to read credentials: {str(e)}")
    
    connection = SheetConnection(credentials_path=credentials_path)
    await connection.connect()
    
    manager = SheetManager(
        connection=connection,
        schema=TestSetup.get_test_schema(),
        encryption_key=encryption_key
    )
    
    yield manager
    
    if manager.sheet_id:
        try:
            await manager.delete_sheet()
        except Exception:
            pass

@pytest.mark.asyncio
async def test_sheet_operations(sheet_manager):
    """Test sheet-level operations."""
    # Test sheet creation
    sheet_id = await sheet_manager.create_sheet("Test Database")
    assert sheet_id is not None
    assert isinstance(sheet_id, str)
    
    # Test sheet rename
    await sheet_manager.rename_sheet("Updated Test Database")
    
    # Sheet deletion is handled by fixture cleanup

@pytest.mark.asyncio
async def test_bulk_operations(sheet_manager):
    """Test bulk data operations."""
    await sheet_manager.create_sheet("Bulk Operations Test")
    
    # Test bulk insert
    test_records = TestSetup.get_test_data(5)
    for record in test_records:
        await sheet_manager.insert(record)
    
    # Verify bulk insert
    all_records = await sheet_manager.read()
    assert len(all_records) == 5
    
    # Test bulk update
    update_result = await sheet_manager.update(
        filters={"name": {"$regex": "Test User"}},
        updates={"salary": 60000.00}
    )
    assert update_result == 5
    
    # Verify update
    updated_records = await sheet_manager.read({"salary": 60000.00})
    assert len(updated_records) == 5
    assert all(r["salary"] == 60000.00 for r in updated_records)

@pytest.mark.asyncio
async def test_validation_rules(sheet_manager):
    """Test schema validation rules."""
    await sheet_manager.create_sheet("Validation Test")
    
    # Test invalid email
    with pytest.raises(ValueError):
        await sheet_manager.insert({
            "id": 1,
            "name": "Test User",
            "email": "invalid-email",
            "age": 30,
            "salary": 50000.00,
            "is_active": True,
            "notes": "Test notes"
        })
    
    # Test age limits
    with pytest.raises(ValueError):
        await sheet_manager.insert({
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "age": 200,
            "salary": 50000.00,
            "is_active": True,
            "notes": "Test notes"
        })
    
    # Test required fields
    with pytest.raises(ValueError):
        await sheet_manager.insert({
            "id": 1,
            "email": "test@example.com"
        })

@pytest.mark.asyncio
async def test_encryption(encryption_key):
    """Test encryption functionality."""
    connection = SheetConnection(credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH"))
    await connection.connect()
    
    schema = TestSetup.get_test_schema(encrypted_fields=["notes"])
    manager = SheetManager(connection, schema, encryption_key=encryption_key)
    
    await manager.create_sheet("Encryption Test")
    
    # Test data with sensitive information
    test_data = TestSetup.get_test_data(1)
    sensitive_note = "SENSITIVE_DATA_123"
    test_data["notes"] = sensitive_note
    
    # Insert with encryption
    await manager.insert(test_data)
    
    # Read back and verify encryption
    records = await manager.read({"id": 1})
    assert len(records) == 1
    
    encrypted_record = records[0]
    assert encrypted_record["notes"] != sensitive_note, "Data was not encrypted"
    
    # Verify decryption
    decrypted_note = manager.encryptor.decrypt(encrypted_record["notes"])
    assert decrypted_note == sensitive_note, "Decryption failed"
    
    await manager.delete_sheet()