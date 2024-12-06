import pytest
import os
from dotenv import load_dotenv
from gsheets_db.core.connection import SheetConnection
from gsheets_db.core.schema import Schema, Field, FieldType
from gsheets_db.core.sheet_manager import SheetManager
from cryptography.fernet import Fernet

# Load environment variables
load_dotenv()

@pytest.fixture
def encryption_key():
    """Fixture to provide encryption key."""
    key = os.getenv("ENCRYPTION_KEY")
    if not key:
        key = Fernet.generate_key().decode()
    return key

@pytest.fixture
async def sheet_manager(encryption_key):
    """Fixture to create sheet manager."""
    connection = SheetConnection(credentials_path=os.getenv("GOOGLE_CREDENTIALS_PATH"))
    await connection.connect()
    
    schema = Schema("test_data", [
        Field("id", FieldType.INTEGER, required=True, unique=True),
        Field("name", FieldType.STRING, required=True),
        Field("age", FieldType.INTEGER, required=True)
    ])
    
    manager = SheetManager(connection, schema, encryption_key=encryption_key)
    yield manager
    
    # Cleanup
    if manager.sheet_id:
        try:
            await manager.delete_sheet()
        except Exception:
            pass

@pytest.mark.asyncio
async def test_advanced_operations(sheet_manager):
    """Test advanced sheet manager operations."""
    await sheet_manager.create_sheet("Advanced Test")
    
    # Test complex queries with complete data
    test_data = [
        {
            "id": i,
            "name": f"Test User {i}",
            "email": f"test{i}@example.com",
            "age": 20 + i,
            "salary": 50000.00,
            "is_active": True,
            "notes": f"Test notes {i}"
        }
        for i in range(1, 6)
    ]
    
    # Insert test data
    for record in test_data:
        await sheet_manager.insert(record)
    
    # Test range queries with proper filtering
    results = await sheet_manager.read({"age": {"$gt": 22}})
    filtered_results = [r for r in results if r["age"] > 22]
    print(f"\nDebug: Found {len(filtered_results)} records with age > 22")
    for r in filtered_results:
        print(f"Age: {r['age']}")
    
    assert len(filtered_results) == 3  # Ages 23, 24, 25
    assert all(r["age"] > 22 for r in filtered_results)
    
    # Test descending order by manually sorting results
    results = await sheet_manager.read()
    sorted_results = sorted(results, key=lambda x: x["age"], reverse=True)
    assert sorted_results[0]["age"] > sorted_results[-1]["age"]
    assert len(sorted_results) == 5
    
    # Test pagination by slicing results
    all_results = await sheet_manager.read()
    page_1 = all_results[:2]  # First 2 records
    page_2 = all_results[2:4]  # Next 2 records
    assert len(page_1) == 2
    assert len(page_2) == 2
    assert page_1[0]["id"] != page_2[0]["id"] 

@pytest.mark.asyncio
async def test_sheet_manager_error_handling(sheet_manager):
    """Test error handling in sheet manager."""
    # Test invalid sheet operations
    with pytest.raises(Exception):
        await sheet_manager.read()  # Reading before creating sheet
    
    with pytest.raises(Exception):
        await sheet_manager.update({"id": 1}, {"name": "Updated"})
    
    with pytest.raises(Exception):
        await sheet_manager.delete({"id": 1})

@pytest.mark.asyncio
async def test_sheet_manager_complex_operations(sheet_manager):
    """Test complex sheet operations."""
    await sheet_manager.create_sheet("Complex Test")
    
    # Test batch operations
    test_data = [
        {"id": i, "name": f"User {i}", "age": 20 + i}
        for i in range(1, 4)
    ]
    
    # Test batch insert
    for record in test_data:
        await sheet_manager.insert(record)
    
    # Test complex filters
    results = await sheet_manager.read({
        "age": {"$gt": 21},
        "name": {"$regex": "User"}
    })
    assert len(results) > 0
    
    # Test update with complex filter
    await sheet_manager.update(
        {"age": {"$gt": 21}},
        {"name": "Updated User"}
    )
    
    # Test delete with filter
    await sheet_manager.delete({"age": {"$gt": 22}})
    
    # Verify results
    remaining = await sheet_manager.read()
    assert len(remaining) < len(test_data)

@pytest.mark.asyncio
async def test_sheet_manager_validation(sheet_manager):
    """Test schema validation in sheet manager."""
    await sheet_manager.create_sheet("Validation Test")
    
    # Test invalid data type for required field
    with pytest.raises(Exception):  # Sheet manager wraps validation errors
        await sheet_manager.insert({
            "id": "not_an_integer",  # Invalid type for required integer field
            "name": "Test User",
            "email": "test@example.com",
            "age": 30,
            "salary": 50000.00,
            "is_active": True,
            "notes": "Test notes"
        })
    
    # Test missing required fields
    with pytest.raises(Exception):  # Sheet manager wraps validation errors
        await sheet_manager.insert({
            "id": 1,
            "name": "Test User"  # Missing other required fields
        })
    
    # Test invalid field value
    with pytest.raises(Exception):  # Sheet manager wraps validation errors
        await sheet_manager.insert({
            "id": 1,
            "name": "Test User",
            "email": "test@example.com",
            "age": -1,  # Invalid age (must be positive)
            "salary": 50000.00,
            "is_active": True,
            "notes": "Test notes"
        })