# GSheetsDB

A Python library that enables using Google Sheets as a database backend with features like schema validation, encryption, and a web dashboard.

## Features

- 🔒 Secure Google Sheets integration with OAuth2
- 📊 Schema validation and type checking
- 🔐 Field-level encryption for sensitive data
- 🌐 Web dashboard for easy management
- 🚀 Async/await support
- 📝 Comprehensive logging
- ⚡ Rate limiting and quota management

## Installation

```bash
pip install gsheets-db
```

## Quick Start

1. Set up Google Cloud Project and enable Google Sheets API:
   - Go to [Google Cloud Console](https://console.cloud.google.com)
   - Create a new project or select existing one
   - Enable Google Sheets API
   - Create OAuth 2.0 credentials
   - Download credentials JSON file

2. Basic Usage:

```python
from gsheets_db.core.connection import SheetConnection
from gsheets_db.core.schema import Schema, Field, FieldType
from gsheets_db.core.sheet import SheetManager
```

### Define your schema

```python
schema = Schema("users", [
    Field("id", FieldType.INTEGER, required=True, unique=True),
    Field("email", FieldType.STRING, required=True),
    Field("password", FieldType.STRING, required=True, encrypted=True)
])
```

### Connect to your Google Sheet

```python
connection = SheetConnection("path/to/credentials.json")
await connection.connect()
```

### Create a new sheet manager

```python
sheet_manager = SheetManager(connection, schema, encryption_key="your-encryption-key")
```

### Create a new sheet

```python
sheet = await sheet_manager.create_sheet("Users Data")
```

### Insert data

```python
await manager.insert({
    "id": 1,
    "email": "user@example.com",
    "password": "secretpass123"
})
```


## Web Dashboard

The library includes a web dashboard for easy management:

```bash
# Install web dependencies
pip install -r requirements.txt

# Run the dashboard
uvicorn gsheets_db.web.app:app --reload
```

Visit `http://localhost:8000` to access the dashboard.

## Schema Definition

Define your data structure with type checking and validation:

```python
from gsheets_db.core.schema import Schema, Field, FieldType, ValidationRule

# Custom validation rule

email_validation = ValidationRule(
        lambda x: "@" in x,
        "Invalid email format"
    )
    schema = Schema("users", [
        Field(
        name="email",
        field_type=FieldType.STRING,
        required=True,
        validation_rules=[email_validation]
    ),
    Field(
        name="age",
        field_type=FieldType.INTEGER,
        min_value=0,
        max_value=150
    ),
    Field(
        name="password",
        field_type=FieldType.STRING,
        min_length=8,
        encrypted=True
    )
])
```

## Security Features

### Field Encryption

Sensitive data can be automatically encrypted:

```python
# Enable encryption for specific fields
schema = Schema("users", [
    Field("ssn", FieldType.STRING, encrypted=True),
    Field("credit_card", FieldType.STRING, encrypted=True)
])

# Provide encryption key when creating manager
manager = SheetManager(connection, schema, encryption_key="your-encryption-key")
```

### Quota Management
Built-in protection against API limits:

```python
from gsheets_db.utils.quota_monitor import QuotaMonitor

# Customize quota limits
quota_monitor = QuotaMonitor(
    'read_requests_per_minute': 1000,
    'write_requests_per_minute': 60
)
```

## Contributing

Contributions are welcome! Please read our [Contributing Guidelines](CONTRIBUTING.md) first.

1. Fork the repository
2. Create your feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.