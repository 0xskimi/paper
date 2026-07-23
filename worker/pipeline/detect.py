"""Detect page size and a safe typing band from letterhead artwork."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import fitz  # PyMuPDF
from PIL import Image


PT_PER_INCH = 72.0
MM_PER_INCH = 25.4
DEFAULT_DPI = 300

PAPER_PRESETS = {
    "a4": (210.0, 297.0),
    "letter": (215.9, 279.4),
}


@dataclass
class MarginsMm:
    top: float
    bottom: float
    left: float
    right: float


@dataclass
class Detection:
    paper: str
    page_width_mm: float
    page_height_mm: float
    dpi: int
    margins: MarginsMm
    header_end_mm: float
    footer_start_mm: float
    notes: List[str]

    def to_dict(self) -> Dict:
        data = asdict(self)
        return data


def pt_to_mm(pt: float) -> float:
    return pt * MM_PER_INCH / PT_PER_INCH


def mm_to_px(mm: float, dpi: int) -> int:
    return int(round(mm / MM_PER_INCH * dpi))


def closest_paper(width_mm: float, height_mm: float) -> str:
    best = "a4"
    best_err = float("inf")
    for name, (w, h) in PAPER_PRESETS.items():
        err = abs(width_mm - w) + abs(height_mm - h)
        if err < best_err:
            best = name
            best_err = err
    return best


def render_pdf_page(pdf_path: Path, out_png: Path, dpi: int = DEFAULT_DPI) -> Tuple[float, float]:
    doc = fitz.open(pdf_path)
    page = doc[0]
    width_mm = pt_to_mm(page.rect.width)
    height_mm = pt_to_mm(page.rect.height)
    zoom = dpi / PT_PER_INCH
    matrix = fitz.Matrix(zoom, zoom)
    pix = page.get_pixmap(matrix=matrix, alpha=False)
    out_png.parent.mkdir(parents=True, exist_ok=True)
    pix.save(str(out_png))
    doc.close()
    return width_mm, height_mm


def normalize_image(image_path: Path, out_png: Path, paper: str = "a4") -> Tuple[float, float]:
    width_mm, height_mm = PAPER_PRESETS.get(paper, PAPER_PRESETS["a4"])
    target_w = mm_to_px(width_mm, DEFAULT_DPI)
    target_h = mm_to_px(height_mm, DEFAULT_DPI)
    with Image.open(image_path) as im:
        rgb = im.convert("RGB")
        fitted = Image.new("RGB", (target_w, target_h), (255, 255, 255))
        scale = min(target_w / rgb.width, target_h / rgb.height)
        new_size = (max(1, int(rgb.width * scale)), max(1, int(rgb.height * scale)))
        resized = rgb.resize(new_size, Image.Resampling.LANCZOS)
        offset = ((target_w - new_size[0]) // 2, (target_h - new_size[1]) // 2)
        fitted.paste(resized, offset)
        out_png.parent.mkdir(parents=True, exist_ok=True)
        fitted.save(out_png, format="PNG")
    return width_mm, height_mm


def row_ink_density(gray: Image.Image) -> List[float]:
    """Mean darkness per row (0 white → 1 ink)."""
    width, height = gray.size
    pixels = gray.load()
    densities: List[float] = []
    for y in range(height):
        total = 0
        for x in range(0, width, 4):  # subsample for speed
            total += 255 - pixels[x, y]
        densities.append((total / ((width // 4) or 1)) / 255.0)
    return densities


def find_content_band(densities: List[float], page_height_mm: float) -> Tuple[float, float]:
    """
    Return (header_end_mm, footer_start_mm) from vertical ink profile.
    Header/footer = outer ink; body = longest low-ink stretch in the middle.
    """
    if not densities:
        return 36.0, page_height_mm - 36.0

    height_px = len(densities)
    # Smooth with a small window
    window = max(3, height_px // 200)
    smooth: List[float] = []
    for i in range(height_px):
        lo = max(0, i - window)
        hi = min(height_px, i + window + 1)
        smooth.append(sum(densities[lo:hi]) / (hi - lo))

    threshold = max(0.02, sorted(smooth)[int(len(smooth) * 0.35)] * 0.85)
    low = [v <= threshold for v in smooth]

    # Longest contiguous low-ink run in the middle 80% of the page
    mid_lo = int(height_px * 0.08)
    mid_hi = int(height_px * 0.92)
    best_start = mid_lo
    best_len = 0
    i = mid_lo
    while i < mid_hi:
        if not low[i]:
            i += 1
            continue
        j = i
        while j < mid_hi and low[j]:
            j += 1
        if j - i > best_len:
            best_len = j - i
            best_start = i
        i = j

    if best_len < height_px * 0.2:
        # Fallback: fixed breathing room
        return 36.0, page_height_mm - 36.0

    best_end = best_start + best_len
    header_end_mm = best_start / height_px * page_height_mm
    footer_start_mm = best_end / height_px * page_height_mm
    return header_end_mm, footer_start_mm


def side_margins_mm(gray: Image.Image, page_width_mm: float) -> Tuple[float, float]:
    """Estimate left/right clear margins from column ink."""
    width, height = gray.size
    pixels = gray.load()
    densities: List[float] = []
    for x in range(width):
        total = 0
        for y in range(0, height, 6):
            total += 255 - pixels[x, y]
        densities.append((total / ((height // 6) or 1)) / 255.0)

    threshold = 0.015
    left_px = 0
    for x, d in enumerate(densities):
        if d > threshold:
            left_px = x
            break
    right_px = width - 1
    for x in range(width - 1, -1, -1):
        if densities[x] > threshold:
            right_px = x
            break

    # Keep body inset from art edges, with a floor
    left_mm = max(12.0, min(28.0, left_px / width * page_width_mm + 4.0))
    right_clear = (width - 1 - right_px) / width * page_width_mm
    right_mm = max(12.0, min(28.0, right_clear + 4.0))
    return left_mm, right_mm


def detect_from_png(png_path: Path, page_width_mm: float, page_height_mm: float, dpi: int = DEFAULT_DPI) -> Detection:
    notes: List[str] = []
    with Image.open(png_path) as im:
        gray = im.convert("L")
        densities = row_ink_density(gray)
        header_end_mm, footer_start_mm = find_content_band(densities, page_height_mm)
        left_mm, right_mm = side_margins_mm(gray, page_width_mm)

    # Breathing room past detected art
    top = min(page_height_mm * 0.35, max(28.0, header_end_mm + 4.0))
    bottom = min(page_height_mm * 0.35, max(28.0, page_height_mm - footer_start_mm + 4.0))

    # Ensure usable body height
    if page_height_mm - top - bottom < 80:
        top = 36.0
        bottom = 36.0
        notes.append("Typing band was tight — used default top/bottom margins.")

    paper = closest_paper(page_width_mm, page_height_mm)
    notes.append(f"Detected clear band below {top:.0f}mm and above {page_height_mm - bottom:.0f}mm.")

    return Detection(
        paper=paper,
        page_width_mm=round(page_width_mm, 2),
        page_height_mm=round(page_height_mm, 2),
        dpi=dpi,
        margins=MarginsMm(
            top=round(top, 1),
            bottom=round(bottom, 1),
            left=round(left_mm, 1),
            right=round(right_mm, 1),
        ),
        header_end_mm=round(header_end_mm, 1),
        footer_start_mm=round(footer_start_mm, 1),
        notes=notes,
    )


def prepare_artwork(
    source_path: Path,
    work_dir: Path,
    paper_hint: Optional[str] = None,
) -> Tuple[Path, Detection]:
    """Normalize any supported upload into a full-page PNG + detection."""
    work_dir.mkdir(parents=True, exist_ok=True)
    out_png = work_dir / "letterhead-full-300dpi.png"
    suffix = source_path.suffix.lower()

    if suffix == ".pdf":
        width_mm, height_mm = render_pdf_page(source_path, out_png)
    elif suffix in {".png", ".jpg", ".jpeg", ".webp"}:
        paper = paper_hint if paper_hint in PAPER_PRESETS else "a4"
        width_mm, height_mm = normalize_image(source_path, out_png, paper=paper)
    else:
        raise ValueError(f"Unsupported file type: {suffix or 'unknown'}")

    detection = detect_from_png(out_png, width_mm, height_mm)
    if paper_hint in PAPER_PRESETS:
        w, h = PAPER_PRESETS[paper_hint]
        detection.paper = paper_hint
        detection.page_width_mm = w
        detection.page_height_mm = h
    return out_png, detection
