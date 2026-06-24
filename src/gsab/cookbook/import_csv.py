"""Recipe: load a CSV into a new sheet. Needs `pip install "gsab[pandas]"`."""

import asyncio

import pandas as pd

from gsab import Field, FieldType, Schema, SheetConnection, SheetManager


async def main(csv_path="data.csv"):
    df = pd.read_csv(csv_path)
    # one Field per column; tweak the types to taste
    schema = Schema(
        "data",
        [Field(col, FieldType.STRING) for col in df.columns],
    )
    db = SheetManager(SheetConnection(), schema)
    await db.create_sheet("Imported data")
    n = await db.from_dataframe(df.astype(str))
    print(f"Imported {n} rows. Tip: `gsab import {csv_path}` does this for you.")


if __name__ == "__main__":
    asyncio.run(main())
