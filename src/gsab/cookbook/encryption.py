"""Recipe: seal sensitive fields with Fernet before they reach the sheet."""

import asyncio

from cryptography.fernet import Fernet

from gsab import Field, FieldType, Schema, SheetConnection, SheetManager

# Generate once and keep it stable (e.g. an env var); you can't decrypt without it.
KEY = Fernet.generate_key().decode()

schema = Schema(
    "people",
    [
        Field("id", FieldType.INTEGER, required=True),
        Field("name", FieldType.STRING),
        Field("ssn", FieldType.STRING, encrypted=True),  # sealed in the sheet
    ],
)


async def main():
    db = SheetManager(SheetConnection(), schema, encryption_key=KEY)
    await db.create_sheet("People")
    await db.insert({"id": 1, "name": "Ada", "ssn": "123-45-6789"})

    # In the sheet the ssn cell is ciphertext; read() decrypts it back:
    print(await db.read({"id": 1}))


if __name__ == "__main__":
    asyncio.run(main())
