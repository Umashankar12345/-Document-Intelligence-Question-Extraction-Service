import io
from typing import List, Dict, Any, Optional
import fitz  # PyMuPDF
from PIL import Image


class PageInfo:
    def __init__(
        self,
        page_number: int,
        raw_text: str,
        is_scanned: bool,
        png_bytes: bytes,
        rotation_deg: int = 0,
        blocks: Optional[List[Dict[str, Any]]] = None,
    ):
        self.page_number = page_number
        self.raw_text = raw_text
        self.is_scanned = is_scanned
        self.png_bytes = png_bytes
        self.rotation_deg = rotation_deg
        self.blocks = blocks or []


def process_pdf(pdf_bytes: bytes, dpi: int = 200) -> List[PageInfo]:
    """
    Open PDF using PyMuPDF, extract native text layer and render high-res PNGs.
    If text density is low, marks page as scanned for downstream OCR.
    """
    try:
        doc = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as e:
        raise ValueError(f"Failed to parse PDF document: {str(e)}")

    if doc.is_encrypted:
        raise ValueError("Encrypted PDFs are not supported")

    pages: List[PageInfo] = []
    zoom = dpi / 72.0
    mat = fitz.Matrix(zoom, zoom)

    for page_idx in range(len(doc)):
        page = doc[page_idx]
        page_num = page_idx + 1

        # Render page to PNG
        pix = page.get_pixmap(matrix=mat, alpha=False)
        png_bytes = pix.tobytes("png")

        # Extract text and layout blocks
        page_dict = page.get_text("blocks")  # (x0, y0, x1, y1, text, block_no, block_type)
        extracted_text = page.get_text("text").strip()

        structured_blocks = []
        for b in page_dict:
            # block_type 0 is text
            if len(b) >= 5 and b[4]:
                structured_blocks.append({
                    "bbox": [round(b[0], 2), round(b[1], 2), round(b[2], 2), round(b[3], 2)],
                    "text": b[4].strip(),
                })

        # Evaluate text density
        word_count = len(extracted_text.split())
        # Scanned page heuristic: fewer than 15 words on a full page
        is_scanned = word_count < 15

        pages.append(
            PageInfo(
                page_number=page_num,
                raw_text=extracted_text,
                is_scanned=is_scanned,
                png_bytes=png_bytes,
                rotation_deg=page.rotation,
                blocks=structured_blocks,
            )
        )

    doc.close()
    return pages


def process_image(image_bytes: bytes) -> List[PageInfo]:
    """
    Process single uploaded image (JPG/PNG/TIFF) into PageInfo with PNG render.
    """
    try:
        img = Image.open(io.BytesIO(image_bytes))
        img.verify()
        # Re-open after verify()
        img = Image.open(io.BytesIO(image_bytes))
        if img.mode != "RGB":
            img = img.convert("RGB")
    except Exception as e:
        raise ValueError(f"Invalid image format: {str(e)}")

    buf = io.BytesIO()
    img.save(buf, format="PNG")
    png_bytes = buf.getvalue()

    return [
        PageInfo(
            page_number=1,
            raw_text="",
            is_scanned=True,  # Raw images always need OCR
            png_bytes=png_bytes,
            rotation_deg=0,
            blocks=[],
        )
    ]
