"""Your GSAB table schema. One Schema = one sheet tab.

Edit the fields, then `app.py` uses this to create and use your sheet.
"""

from gsab import Field, FieldType, Schema

users = Schema(
    "users",
    [
        Field("id", FieldType.INTEGER, required=True, unique=True),
        Field("name", FieldType.STRING, required=True, max_length=80),
        Field("email", FieldType.STRING, pattern=r"[^@]+@[^@]+\.[^@]+"),
        Field("plan", FieldType.STRING, default="free"),
    ],
)
