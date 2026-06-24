"""Recipe: filter/sort/aggregate on Google's side with query() (not in Python)."""

import asyncio

from gsab import Field, FieldType, Schema, SheetConnection, SheetManager

schema = Schema(
    "laptops",
    [
        Field("brand", FieldType.STRING, required=True),  # column A
        Field("model", FieldType.STRING),  # column B
        Field("ram_gb", FieldType.INTEGER),  # column C
        Field("price_eur", FieldType.FLOAT),  # column D
    ],
)


async def main():
    db = SheetManager(SheetConnection(), schema)
    await db.create_sheet("Laptops")
    await db.bulk_insert(
        [
            {"brand": "Dell", "model": "XPS 13", "ram_gb": 16, "price_eur": 1299.0},
            {"brand": "Apple", "model": "MacBook Air", "ram_gb": 8, "price_eur": 1199.0},
            {"brand": "Asus", "model": "Zephyrus", "ram_gb": 32, "price_eur": 1899.0},
        ]
    )

    # columns are letters; db.column("price_eur") -> "D"
    print("over 1000, dearest first:", await db.query("SELECT A, D WHERE D > 1000 ORDER BY D DESC"))
    print("average price:", await db.query("SELECT AVG(D)"))


if __name__ == "__main__":
    asyncio.run(main())
