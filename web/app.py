from fastapi import FastAPI, HTTPException, Depends, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from typing import Dict, Any, Optional, List
import os
from pathlib import Path
from fastapi.security import OAuth2AuthorizationCodeBearer

from ..core.connection import SheetConnection
from ..core.sheet_manager import SheetManager
from ..core.schema import Schema, Field, FieldType
from ..auth.authenticator import GoogleAuthenticator
from .auth import auth_manager, get_current_user
from google.oauth2.credentials import Credentials

app = FastAPI(title="GSheetsDB Dashboard")

# Setup templates and static files
BASE_DIR = Path(__file__).resolve().parent
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "static")), name="static")

class AppState:
    def __init__(self):
        self.connection = None
        self.sheet_manager = None
        self.credentials_path = None

app_state = AppState()

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the home page."""
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "is_connected": app_state.connection is not None}
    )

@app.post("/connect")
async def connect(credentials_path: str):
    """Connect to Google Sheets."""
    try:
        app_state.credentials_path = credentials_path
        app_state.connection = SheetConnection(credentials_path)
        await app_state.connection.connect()
        return {"status": "success", "message": "Connected to Google Sheets"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/create-sheet")
async def create_sheet(
    title: str,
    schema_definition: Dict[str, Any],
    credentials: Credentials = Depends(get_current_user)
):
    """Create a new sheet with the specified schema."""
    if not app_state.connection:
        raise HTTPException(status_code=400, detail="Not connected to Google Sheets")
    
    try:
        # Convert schema definition to Schema object
        fields = [
            Field(
                name=field["name"],
                field_type=FieldType[field["type"].upper()],
                required=field.get("required", True),
                encrypted=field.get("encrypted", False)
            )
            for field in schema_definition["fields"]
        ]
        
        schema = Schema(schema_definition["name"], fields)
        app_state.sheet_manager = SheetManager(
            app_state.connection,
            schema,
            encryption_key=schema_definition.get("encryption_key")
        )
        
        sheet_id = await app_state.sheet_manager.create_sheet(title)
        return {
            "status": "success",
            "sheet_id": sheet_id,
            "message": f"Created sheet: {title}"
        }
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.post("/insert-data")
async def insert_data(data: Dict[str, Any]):
    """Insert data into the sheet."""
    if not app_state.sheet_manager:
        raise HTTPException(status_code=400, detail="No sheet selected")
    
    try:
        await app_state.sheet_manager.insert(data)
        return {"status": "success", "message": "Data inserted successfully"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/auth/login")
async def login():
    """Start OAuth2 login flow."""
    return {"authorization_url": auth_manager.get_authorization_url()}

@app.get("/auth/callback")
async def auth_callback(code: str):
    """Handle OAuth2 callback."""
    try:
        credentials = await auth_manager.handle_callback(code)
        app_state.connection = SheetConnection(credentials=credentials)
        await app_state.connection.connect()
        return {"status": "success", "message": "Authentication successful"}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e)) 