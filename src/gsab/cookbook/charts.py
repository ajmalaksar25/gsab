"""Recipe: native in-sheet charts, or hand the data to matplotlib/Plotly."""

import asyncio

from gsab import Field, FieldType, Schema, SheetConnection, SheetManager

schema = Schema(
    "sales",
    [
        Field("month", FieldType.STRING, required=True),
        Field("revenue", FieldType.FLOAT),
        Field("cost", FieldType.FLOAT),
    ],
)


async def main():
    db = SheetManager(SheetConnection(), schema)
    await db.create_sheet("Sales")
    await db.bulk_insert(
        [
            {"month": "Jan", "revenue": 1200.0, "cost": 800.0},
            {"month": "Feb", "revenue": 1500.0, "cost": 900.0},
            {"month": "Mar", "revenue": 1700.0, "cost": 950.0},
        ]
    )

    # native chart drawn in the sheet (no extra deps)
    await db.chart(x="month", y=["revenue", "cost"], kind="LINE", title="Revenue vs cost")

    # ...or plot in Python (needs the pandas extra + your plotting lib):
    # df = await db.to_dataframe()
    # df.plot(x="month", y=["revenue", "cost"])
    print("Added a LINE chart to the sheet.")


if __name__ == "__main__":
    asyncio.run(main())
