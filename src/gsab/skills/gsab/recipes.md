# GSAB recipes

Copy-paste patterns. All async — run inside `asyncio.run(...)`.

## Pull a CSV into a new sheet

```python
import pandas as pd
from gsab import SheetConnection, SheetManager, Schema, Field, FieldType

df = pd.read_csv("laptops.csv")
schema = Schema("laptops", [
    Field("brand", FieldType.STRING, required=True),
    Field("model", FieldType.STRING),
    Field("ram_gb", FieldType.INTEGER),
    Field("price_eur", FieldType.FLOAT),
])

db = SheetManager(SheetConnection(), schema)
await db.create_sheet("Laptops")
n = await db.from_dataframe(df)        # bulk insert every row; returns count
```

## Server-side query (filter/sort/aggregate on Google's side)

```python
# columns are letters: A=brand, B=model, C=ram_gb, D=price_eur
top = await db.query("SELECT A, D WHERE D > 1000 ORDER BY D DESC LIMIT 5")
avg = await db.query("SELECT AVG(D)")           # aggregates stay gviz-native
db.column("price_eur")                          # -> "D"
```

## Read into pandas and plot / analyze

```python
out = await db.to_dataframe({"ram_gb": {"$gte": 16}})
out.describe()
# native in-sheet chart instead of a Python plot:
await db.chart(x="brand", y="price_eur", kind="BAR", title="Price by brand")
```

## Encrypted fields

```python
from cryptography.fernet import Fernet
key = Fernet.generate_key().decode()            # store in an env var; keep it stable

schema = Schema("users", [
    Field("id", FieldType.INTEGER, required=True),
    Field("ssn", FieldType.STRING, encrypted=True),
])
db = SheetManager(SheetConnection(), schema, encryption_key=key)
await db.create_sheet("Users")
await db.insert({"id": 1, "ssn": "123-45-6789"})   # sealed before it reaches the sheet
rows = await db.read()                              # decrypted on read
```

## Robust error handling

```python
from gsab import GSABError, AuthError, NotFoundError, ValidationError

try:
    await db.query("SELECT bogus")
except ValidationError as e:
    print("bad query:", e)        # also a ValueError
except AuthError:
    print("run `gsab auth login`")
except GSABError as e:
    print("gsab error:", e)       # catch-all; transient errors already retried
```

## Use an existing spreadsheet (instead of create_sheet)

```python
db = SheetManager(SheetConnection(), schema)
db.sheet_id = "1AbC...your-spreadsheet-id"     # the tab must match schema.name
rows = await db.read()
```

## Servers / CI (no browser)

```bash
export GSAB_SERVICE_ACCOUNT=/path/to/service-account.json
# share the spreadsheet with the service account's email, then:
python your_app.py     # SheetConnection() picks it up automatically
```
