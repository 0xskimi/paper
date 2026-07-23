"""Paper worker — upload letterhead art, detect margins, export Word templates."""

from __future__ import annotations

import json
import re
import shutil
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from pipeline.build import BuildOptions, MarginsMm, options_from_detection, write_packages
from pipeline.detect import PAPER_PRESETS, prepare_artwork

ROOT = Path(__file__).resolve().parent
JOBS = ROOT / "jobs"
JOBS.mkdir(parents=True, exist_ok=True)

ALLOWED_EXT = {".pdf", ".png", ".jpg", ".jpeg", ".webp"}
MAX_BYTES = 25 * 1024 * 1024

app = FastAPI(title="Paper", version="0.1.0")

CORS_ORIGINS = [
    "https://paper.tentacore.xyz",
    "https://tentacore.xyz",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.mount("/api/files", StaticFiles(directory=JOBS), name="files")


class MarginsIn(BaseModel):
    top: float = Field(ge=10, le=120)
    bottom: float = Field(ge=10, le=120)
    left: float = Field(ge=8, le=60)
    right: float = Field(ge=8, le=60)


class RebuildIn(BaseModel):
    margins: MarginsIn
    paper: Optional[str] = None
    font_name: str = "Calibri"


def slugify(name: str) -> str:
    stem = Path(name).stem
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", stem).strip("-._")
    return cleaned[:60] or "letterhead"


def job_dir(job_id: str) -> Path:
    path = JOBS / job_id
    if not path.exists():
        raise HTTPException(status_code=404, detail="Job not found")
    return path


def read_meta(path: Path) -> Dict[str, Any]:
    meta_path = path / "meta.json"
    if not meta_path.exists():
        raise HTTPException(status_code=404, detail="Job metadata missing")
    return json.loads(meta_path.read_text())


def write_meta(path: Path, meta: Dict[str, Any]) -> None:
    (path / "meta.json").write_text(json.dumps(meta, indent=2))


def public_urls(job_id: str, basename: str) -> Dict[str, str]:
    base = f"/api/files/{job_id}"
    return {
        "previewUrl": f"{base}/letterhead-full-300dpi.png",
        "docxUrl": f"{base}/{basename}.docx",
        "dotxUrl": f"{base}/{basename}.dotx",
    }


@app.get("/api/health")
def health():
    return {"ok": True}


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    paper: Optional[str] = Form(default=None),
):
    filename = file.filename or "letterhead.pdf"
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_EXT:
        raise HTTPException(status_code=400, detail="Use PDF, PNG, JPG, or WebP.")

    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=400, detail="Empty file.")
    if len(raw) > MAX_BYTES:
        raise HTTPException(status_code=400, detail="File too large (25MB max).")

    job_id = uuid.uuid4().hex[:12]
    path = JOBS / job_id
    path.mkdir(parents=True, exist_ok=True)
    source = path / f"source{suffix}"
    source.write_bytes(raw)

    basename = slugify(filename)
    try:
        artwork, detection = prepare_artwork(
            source,
            path,
            paper_hint=paper if paper in PAPER_PRESETS else None,
        )
        options = options_from_detection(detection)
        write_packages(artwork, options, path, basename)
    except Exception as exc:  # noqa: BLE001
        shutil.rmtree(path, ignore_errors=True)
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    meta = {
        "id": job_id,
        "filename": filename,
        "basename": basename,
        "detection": detection.to_dict(),
        "margins": detection.margins.__dict__,
        "paper": detection.paper,
        "fontName": "Calibri",
        "steps": [
            {"id": "read", "label": "Read your page", "done": True},
            {"id": "raster", "label": "Rasterize artwork at 300 DPI", "done": True},
            {"id": "detect", "label": "Find safe typing band", "done": True},
            {"id": "build", "label": "Package Word letterhead", "done": True},
        ],
    }
    write_meta(path, meta)

    return {
        "job": meta,
        "urls": public_urls(job_id, basename),
    }


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str):
    path = job_dir(job_id)
    meta = read_meta(path)
    return {
        "job": meta,
        "urls": public_urls(job_id, meta["basename"]),
    }


@app.post("/api/jobs/{job_id}/rebuild")
def rebuild_job(job_id: str, body: RebuildIn):
    path = job_dir(job_id)
    meta = read_meta(path)
    artwork = path / "letterhead-full-300dpi.png"
    if not artwork.exists():
        raise HTTPException(status_code=404, detail="Artwork missing.")

    detection = meta["detection"]
    paper = body.paper if body.paper in PAPER_PRESETS else meta.get("paper", detection["paper"])
    width_mm, height_mm = PAPER_PRESETS[paper]

    margins = MarginsMm(
        top=body.margins.top,
        bottom=body.margins.bottom,
        left=body.margins.left,
        right=body.margins.right,
    )
    options = BuildOptions(
        margins=margins,
        page_width_mm=width_mm,
        page_height_mm=height_mm,
        font_name=body.font_name or "Calibri",
    )
    basename = meta["basename"]
    write_packages(artwork, options, path, basename)

    meta["margins"] = margins.__dict__
    meta["paper"] = paper
    meta["fontName"] = options.font_name
    meta["detection"]["paper"] = paper
    meta["detection"]["page_width_mm"] = width_mm
    meta["detection"]["page_height_mm"] = height_mm
    meta["detection"]["margins"] = margins.__dict__
    write_meta(path, meta)

    return {
        "job": meta,
        "urls": public_urls(job_id, basename),
    }


@app.get("/api/jobs/{job_id}/download/{kind}")
def download(job_id: str, kind: str):
    if kind not in {"docx", "dotx"}:
        raise HTTPException(status_code=400, detail="kind must be docx or dotx")
    path = job_dir(job_id)
    meta = read_meta(path)
    file_path = path / f"{meta['basename']}.{kind}"
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    media = (
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
        if kind == "docx"
        else "application/vnd.openxmlformats-officedocument.wordprocessingml.template"
    )
    return FileResponse(
        file_path,
        media_type=media,
        filename=file_path.name,
    )
