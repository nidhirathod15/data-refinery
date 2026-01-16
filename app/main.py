# app/main.py: THE HEART

import os
import shutil
import pandas as pd
from fastapi import FastAPI, UploadFile, File, Request
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from .core.engine import RefineryEngine

app = FastAPI()

# Configuration
UPLOAD_DIR = "uploads"
os.makedirs(UPLOAD_DIR, exist_ok=True)

# Setup Templates and Static files
templates = Jinja2Templates(directory="app/templates")
# app.mount("/static", StaticFiles(directory="app/static"), name="static")

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.post("/process", response_class=HTMLResponse)
async def process_data(request: Request, file: UploadFile = File(...)):
    try:
        print(f"--- Processing Started: {file.filename} ---")
        
        # 1. Define Paths
        original_path = os.path.join(UPLOAD_DIR, file.filename)
        cleaned_filename = f"cleaned_{file.filename}"
        cleaned_path = os.path.join(UPLOAD_DIR, cleaned_filename)

        # 2. Save Uploaded File
        with open(original_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
        print(f"File saved to: {original_path}")

        # 3. Process with Engine
        engine = RefineryEngine(original_path)
        cleaned_df = engine.process()
        print("Engine processing complete.")

        # 4. Save Cleaned File
        if file.filename.endswith('.csv'):
            cleaned_df.to_csv(cleaned_path, index=False)
        else:
            cleaned_df.to_excel(cleaned_path, index=False)
        print(f"Cleaned file saved to: {cleaned_path}")

        # 5. Create Preview (HTML Table)
        preview_html = cleaned_df.head(15).to_html(classes="table table-striped table-hover", index=False)

        print("--- Success: Sending data to UI ---")
        return templates.TemplateResponse("index.html", {
            "request": request,
            "message": "Dataset refined and categorized successfully!",
            "preview": preview_html,
            "download_link": f"/download/{cleaned_filename}"
        })

    except Exception as e:
        import traceback
        print(traceback.format_exc()) # This prints the FULL error path in your terminal
        return templates.TemplateResponse("index.html", {
            "request": request, 
            "error": f"Processing failed: {str(e)}"
        })

@app.get("/download/{filename}")
async def download_file(filename: str):
    file_path = os.path.join(UPLOAD_DIR, filename)
    if os.path.exists(file_path):
        return FileResponse(path=file_path, filename=filename)
    return {"error": "File not found"}