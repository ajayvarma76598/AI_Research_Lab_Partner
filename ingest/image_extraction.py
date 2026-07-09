import logging
from pathlib import Path
from typing import List, Dict, Any
import fitz  # PyMuPDF

logger = logging.getLogger(__name__)


def extract_images_from_pdf(pdf_path: str, output_dir: str) -> List[Dict[str, Any]]:
    """
    Extract images from a PDF document.

    Args:
        pdf_path: Path to the PDF file
        output_dir: Directory to save extracted images

    Returns:
        List of dicts: {"path": ..., "page": ..., "image_index": ...}
    """
    logger.info(f"Opening PDF file: {pdf_path}")
    doc = fitz.open(pdf_path)
    total_pages = len(doc)
    logger.info(f"PDF opened successfully, total pages: {total_pages}")

    results = []
    for page_index in range(total_pages):
        page = doc.load_page(page_index)
        images = page.get_images(full=True)

        if not images:
            continue

        logger.info(f"Found {len(images)} image(s) on page {page_index + 1}")

        for img_index, img in enumerate(images):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]
            ext = base_image.get("ext", "png")
            out_path = Path(output_dir) / f"extracted_image_page{page_index}_img{img_index}.{ext}"

            with open(out_path, "wb") as f:
                f.write(image_bytes)

            results.append({
                "path": str(out_path),
                "page": page_index,
                "image_index": img_index,
            })

    logger.info(f"Extracted {len(results)} image(s) total from {pdf_path}")
    return results
