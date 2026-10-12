import re
import time
import uuid
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.templating import Jinja2Templates

from .core.engine import RefineryEngine, is_supported_file

BASE_DIR = Path(__file__).resolve().parent
UPLOAD_DIR = Path("uploads")
UPLOAD_DIR.mkdir(exist_ok=True)

MAX_UPLOAD_BYTES = 10 * 1024 * 1024      # 10 MB
MAX_FILE_AGE_SECONDS = 60 * 60           # delete files after 1 hour
_SAFE_DOWNLOAD = re.compile(r"^[0-9a-f]{32}_cleaned\.(csv|xlsx)$")

app = FastAPI(title="DataRefinery")
templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))


def cleanup_old_files(max_age=MAX_FILE_AGE_SECONDS):
    now = time.time()
    for f in UPLOAD_DIR.iterdir():
        if f.is_file() and now - f.stat().st_mtime > max_age:
            f.unlink(missing_ok=True)


@app.get("/", response_class=HTMLResponse)
def read_root(request: Request):
    return templates.TemplateResponse(request, "index.html", {})


# Plain `def` (not async): pandas/embedding work is CPU-bound and FastAPI runs it
# in a thread pool instead of blocking the event loop.
@app.post("/process", response_class=HTMLResponse)
def process_data(request: Request, file: UploadFile = File(...)):
    cleanup_old_files()
    original_name = file.filename or ""
    if not is_supported_file(original_name):
        return templates.TemplateResponse(
            request, "index.html", {"error": "Please upload a .csv or .xlsx file."}, status_code=400)

    suffix = Path(original_name).suffix.lower()          # never use the user's filename on disk
    job_id = uuid.uuid4().hex
    original_path = UPLOAD_DIR / f"{job_id}{suffix}"
    out_suffix = ".csv" if suffix == ".csv" else ".xlsx"
    cleaned_name = f"{job_id}_cleaned{out_suffix}"
    cleaned_path = UPLOAD_DIR / cleaned_name

    try:
        data = file.file.read(MAX_UPLOAD_BYTES + 1)
        if len(data) > MAX_UPLOAD_BYTES:
            return templates.TemplateResponse(
                request, "index.html", {"error": "File too large (max 10 MB)."}, status_code=413)
        original_path.write_bytes(data)

        engine = RefineryEngine(original_path)
        cleaned_df = engine.process()

        if out_suffix == ".csv":
            cleaned_df.to_csv(cleaned_path, index=False)
        else:
            cleaned_df.to_excel(cleaned_path, index=False)

        preview_html = cleaned_df.head(15).to_html(
            classes="table table-striped table-hover", index=False)
        return templates.TemplateResponse(request, "index.html", {
            "message": "Dataset refined and categorized successfully!",
            "preview": preview_html,
            "report": engine.report,
            "download_link": f"/download/{cleaned_name}",
        })
    except Exception as e:
        print(f"[ERROR] processing failed: {e!r}")      # full detail stays in the server log
        return templates.TemplateResponse(
            request, "index.html",
            {"error": "Could not process this file. Check that it is a valid CSV/XLSX."},
            status_code=422)
    finally:
        original_path.unlink(missing_ok=True)           # keep only the cleaned output


@app.get("/download/{filename}")
def download_file(filename: str):
    if not _SAFE_DOWNLOAD.match(filename):
        raise HTTPException(status_code=404, detail="File not found")
    path = UPLOAD_DIR / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(path=path, filename=f"cleaned{path.suffix}")
