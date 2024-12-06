# Google Sheets as Backend (GSAB)

A Python library that enables using Google Sheets as a database backend with features like schema validation and encryption.

## Features

- 🔒 Secure Google Sheets integration with OAuth2
- 📊 Schema validation and type checking
- 🔐 Field-level encryption for sensitive data
- 🌐 Async/await support
- 📝 Comprehensive logging

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

2. Set up environment variables:

```bash
GOOGLE_CREDENTIALS_PATH=/path/to/credentials.json
ENCRYPTION_KEY=your-encryption-key
```

3. Basic Usage:

```python
from gsab import SheetConnection, Schema, Field, FieldType, SheetManager

# Define your schema
schema = Schema("users", [
    Field("id", FieldType.INTEGER, required=True, unique=True),
    Field("email", FieldType.STRING, required=True),
    Field("password", FieldType.STRING, required=True, encrypted=True)
])

# Connect and use
async def main():
    connection = SheetConnection()
    await connection.connect()
    
    sheet_manager = SheetManager(connection, schema)
    
    # Create a new sheet
    sheet = await sheet_manager.create_sheet("Users Data")
    
    # Insert data
    await sheet_manager.insert({
        "id": 1,
        "email": "user@example.com",
        "password": "secretpass123"  # Will be automatically encrypted
    })

```

## Schema Definition

Define your data structure with type checking and validation:

```python
from gsab import Schema, Field, FieldType, ValidationRule

schema = Schema("users", [
    Field("id", FieldType.INTEGER, required=True, unique=True),
    Field("email", FieldType.STRING, required=True),
    Field("age", FieldType.INTEGER, min_value=0, max_value=150),
    Field("password", FieldType.STRING, required=True, encrypted=True)
])
```

## Security Features

### Field Encryption

Sensitive data is automatically encrypted when the field is marked with `encrypted=True`:

```python
# Fields marked as encrypted will be automatically handled
schema = Schema("users", [
    Field("ssn", FieldType.STRING, encrypted=True),
    Field("credit_card", FieldType.STRING, encrypted=True)
])
```

<!-- ## Contributing

We love your input! We want to make contributing to GSheetsDB as easy and transparent as possible, whether it's:

- Reporting a bug
- Discussing the current state of the code
- Submitting a fix
- Proposing new features
- Becoming a maintainer

Check out our [Contributing Guide](CONTRIBUTING.md) for ways to get started. -->

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.

[![PyPI version](https://badge.fury.io/py/gsab.svg)](https://badge.fury.io/py/gsab)
[![Tests](https://github.com/ajmalaksar25/gsab/actions/workflows/tests.yml/badge.svg)](https://github.com/ajmalaksar25/gsab/actions/workflows/tests.yml)
[![codecov](https://codecov.io/gh/ajmalaksar25/gsab/branch/main/graph/badge.svg)](https://codecov.io/gh/ajmalaksar25/gsab)