"""Recipe: a tiny live dashboard over a sheet with Streamlit.

A "connect a UI to your sheet" starter — an interactive, sortable, cross-filterable
table (st.dataframe) plus a chart, refreshed from GSAB on each interaction. The
closest Python analog to a TanStack-style data table with almost no code.

    pip install "gsab[pandas]" streamlit
    gsab cookbook show dashboard --out dashboard.py
    # set SHEET_ID below (a sheet you created with GSAB), then:
    streamlit run dashboard.py

For a heavier, AG-Grid-grade table (grouping, pivoting), swap st.dataframe for
`dash` + `dash-ag-grid`, or `nicegui`'s `ui.aggrid` — both render the same dicts
that read()/query() return.
"""

import asyncio

import streamlit as st

from gsab import Field, FieldType, Schema, SheetConnection, SheetManager

SHEET_ID = "PUT-YOUR-SPREADSHEET-ID-HERE"

schema = Schema(
    "users",
    [
        Field("id", FieldType.INTEGER, primary_key=True),
        Field("name", FieldType.STRING),
        Field("plan", FieldType.STRING, default="free"),
        Field("price", FieldType.FLOAT, default=0.0),
    ],
)


@st.cache_resource
def get_db():
    db = SheetManager(SheetConnection(), schema)
    db.sheet_id = SHEET_ID
    return db


async def load(plan):
    db = get_db()
    return await db.to_dataframe({"plan": plan} if plan else None)


st.title("📊 GSAB dashboard")
st.caption("A Google Sheet, served as a live, filterable table.")

plan = st.sidebar.selectbox("Filter by plan", ["(all)", "free", "pro", "team"])
df = asyncio.run(load(None if plan == "(all)" else plan))

st.dataframe(df, use_container_width=True)  # sortable / searchable table
if not df.empty and "price" in df:
    st.bar_chart(df.set_index("name")["price"])
if st.button("Refresh"):
    st.rerun()
