"""Runnable GSAB starter.

    pip install gsab
    gsab auth login        # one-time browser sign-in
    python app.py
"""

import asyncio

from gsab import SheetConnection, SheetManager
from schema import users


async def main():
    db = SheetManager(SheetConnection(), users)
    sheet_id = await db.create_sheet("My GSAB App")
    print("Created sheet:", sheet_id)

    await db.insert({"id": 1, "name": "Ada Lovelace", "email": "ada@calc.org", "plan": "pro"})
    await db.insert({"id": 2, "name": "Alan Turing", "email": "alan@enigma.io"})

    # upsert = insert-or-update on the primary key (id). Safe to re-run; here it
    # upgrades Alan (id=2) to pro without duplicating the row.
    print("Upsert:", await db.upsert({"id": 2, "plan": "pro"}))  # -> "updated"

    print("Pro users (read):", await db.read({"plan": "pro"}))
    print("Server-side query:", await db.query("SELECT A, B WHERE D = 'pro'"))

    await db.chart(x="name", y="id", kind="COLUMN", title="Users")
    print("Done — open the sheet in Google Sheets to see your data and chart.")


if __name__ == "__main__":
    asyncio.run(main())
