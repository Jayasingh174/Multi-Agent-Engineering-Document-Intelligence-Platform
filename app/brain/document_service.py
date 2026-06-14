import os
import logging
from typing import List, Dict, Any, Optional

# Extraction services
from app.services.pdf_service import extract_pdf
from app.services.docx_service import extract_docx
from app.services.csv_service import extract_csv
from app.services.excel_service import extract_boq_data
from app.services.text_service import extract_text
from app.services.cad_service import extract_dwg, summarize_dxf

# AI pipeline services
from app.brain.chunk_service import chunk_text
from app.brain.embedding_service import embed_texts
from app.brain.vector_service import vector_store 

from app.config import DWG_TEMP_DIR

logger = logging.getLogger(__name__)

MAX_FILE_SIZE = 10 * 1024 * 1024  # 10MB
SUPPORTED_EXTENSIONS = {
    ".pdf", ".docx", ".csv", ".xlsx", ".xls", ".txt", ".dwg", ".dxf"
}
MIN_TEXT_LENGTH = 10
MIN_CHUNK_LENGTH = 20


# ==========================================
# 🛠️ HELPER FUNCTIONS
# ==========================================

def get_fuzzy_val(row_dict: dict, possible_keys: List[str]) -> str:
    """Checks a dictionary for multiple possible column names (case-insensitive)."""
    if not isinstance(row_dict, dict):
        return ""
        
    lower_row = {str(k).lower().strip(): v for k, v in row_dict.items() if k}
    
    for key in possible_keys:
        if key.lower() in lower_row and lower_row[key.lower()] is not None:
            return str(lower_row[key.lower()]).strip()
    return ""


def _process_excel_boq(file_path: str) -> tuple[str, List[str]]:
    """Handles specific extraction logic for BOQ Excel spreadsheets."""
    boq_data = extract_boq_data(file_path)
    if not boq_data:
        raise ValueError("No data extracted from Excel")

    chunks = []
    for row in boq_data:
        if not row or not isinstance(row, dict):
            continue

        item = get_fuzzy_val(row, ["Item", "Item No", "S.No", "ID", "No."])
        desc = get_fuzzy_val(row, ["Material", "Description", "Item Description", "Name", "Spec"])
        qty = get_fuzzy_val(row, ["Quantity", "Qty", "Qty.", "Amount"])
        unit = get_fuzzy_val(row, ["Unit", "UOM", "Unit of Measure"])

        if not desc and not qty:
            continue

        text_chunk = f"Item {item}: {desc} | Qty: {qty} {unit}"
        chunks.append(text_chunk)

    logger.info(f"📊 Excel processed → {len(chunks)} BOQ chunks extracted")
    return "\n".join(chunks), chunks


def _extract_raw_text(file_path: str, ext: str) -> str:
    """Routes the file to the correct parser based on extension."""
    raw: Any = ""
    
    if ext == ".pdf":
        raw = extract_pdf(file_path)
    elif ext == ".docx":
        raw = extract_docx(file_path)
    elif ext == ".csv":
        raw = extract_csv(file_path)
    elif ext == ".txt":
        raw = extract_text(file_path)
    elif ext == ".dwg":
        raw = extract_dwg(file_path, DWG_TEMP_DIR)
    elif ext == ".dxf":
        raw = summarize_dxf({"file_path": file_path})

    # Handle varying return types from parsers (string vs. dict)
    if isinstance(raw, dict):
        text_chunks = raw.get("text_chunks", [])
        summary = raw.get("summary", "")
        return f"{summary}\n\n{' '.join(text_chunks)}"
    
    return str(raw)


# ==========================================
# 🧠 MAIN PIPELINE FUNCTION
# ==========================================

async def process_document(file_path: str) -> str:
    """
    Ingests a document, extracts text/BOQ data, chunks it, 
    generates embeddings, and stores it in the vector database.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        raise ValueError("File exceeds maximum allowed size (10MB)")

    ext = os.path.splitext(file_path)[1].lower()
    if ext not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {ext}")

    filename = os.path.basename(file_path)
    logger.info(f"Initiating processing for: {filename}")

    try:
        chunks: List[str] = []
        clean_text: str = ""

        # 1️⃣ EXTRACTION & PRE-CHUNKING
        if ext in [".xlsx", ".xls"]:
            # Dedicated pathway for highly structured BOQ data
            clean_text, chunks = _process_excel_boq(file_path)
        else:
            # Standard pathway for unstructured documents & CAD
            clean_text = _extract_raw_text(file_path, ext).strip()
            
            if len(clean_text) < MIN_TEXT_LENGTH:
                raise ValueError("No meaningful text extracted from document.")

            raw_chunks = chunk_text(clean_text)
            chunks = [c.strip() for c in raw_chunks if c and len(c.strip()) > MIN_CHUNK_LENGTH]
            logger.info(f"📄 Text processed → {len(chunks)} chunks generated")

        if not chunks:
            raise ValueError("Extraction yielded no valid chunks for embedding.")

        # 2️⃣ EMBEDDINGS
        embeddings = await embed_texts(chunks)
        if embeddings is None or len(embeddings) == 0:
            raise ValueError("Embedding generation returned empty or None.")

        # 3️⃣ VECTOR STORAGE
        vector_store.add_documents(
            chunks=chunks,
            embeddings=embeddings,
            source_filename=filename
        )

        logger.info(f"✅ Document successfully indexed: {filename}")
        return clean_text

    except Exception as e:
        logger.error(f"❌ Document processing failed: {file_path} | Error: {str(e)}", exc_info=True)
        raise RuntimeError(f"Pipeline failure for {filename}: {str(e)}") from e