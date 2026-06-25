"""Recipe: idempotent writes with a primary key — insert-or-update via upsert()."""

import asyncio

from gsab import Field, FieldType, Schema, SheetConnection, SheetManager


def schema():
    return Schema(
        "users",
        [
            Field("id", FieldType.INTEGER, primary_key=True),  # enforced unique key
            Field("name", FieldType.STRING),
            Field("plan", FieldType.STRING, default="free"),
        ],
    )


async def main():
    db = SheetManager(SheetConnection(), schema())
    await db.create_sheet("Upsert demo")

    await db.insert({"id": 1, "name": "Ada", "plan": "pro"})

    # Re-running the same logic is safe: upsert updates id=1 instead of duplicating.
    # Fields you omit keep their current value (here: name stays "Ada").
    print(await db.upsert({"id": 1, "plan": "free"}))  # -> "updated"
    print(await db.upsert({"id": 2, "name": "Lin"}))   # -> "inserted"

    # Bulk insert-or-update; last entry wins for a repeated key.
    print(await db.bulk_upsert([{"id": 1, "plan": "pro"}, {"id": 3, "name": "Eve"}]))
    # -> {"inserted": 1, "updated": 1}

    print(await db.read())

    # Note: upsert is a read-check-write — Google Sheets has no conditional write —
    # so two concurrent upserts of the same NEW key can both insert. Plain insert()
    # of a duplicate key raises DuplicateKeyError.


if __name__ == "__main__":
    asyncio.run(main())
