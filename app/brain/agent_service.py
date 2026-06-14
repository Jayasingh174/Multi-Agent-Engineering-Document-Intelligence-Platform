

import os
import json
import asyncio
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, cast

import pandas as pd
from pydantic import BaseModel, ValidationError
from openai import AsyncOpenAI

# 🐛 FIX 1: Import UPLOAD_DIR from your config
from app.config import MAX_RETRIES, OPENAI_MODEL, UPLOAD_DIR

# ==========================================
# ⚙️ CONFIGURATION & SETUP
# ==========================================
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# Convert UPLOAD_DIR to a Path object so .iterdir() and .exists() work safely
UPLOAD_PATH = Path(UPLOAD_DIR)

# ==========================================
# 🧩 PYDANTIC MODELS (Data Contracts)
# ==========================================
class DocOutput(BaseModel):
    project_type: str
    key_requirements: List[str]
    clean_text: str

class BOQItem(BaseModel):
    item: str
    quantity: float = 0.0  # <-- Add '= 0.0' as a safe default fallback
    unit: str


class BOQOutput(BaseModel):
    boq_items: List[BOQItem]

class RiskOutput(BaseModel):
    risks: List[str]
    risk_level: str

class SummaryOutput(BaseModel):
    summary: str
    key_points: List[str]


# ==========================================
# 🔁 CORE LLM SERVICE (Strict Validation)
# ==========================================
async def safe_structured_llm_call(prompt: str, response_model: type[BaseModel]) -> BaseModel | dict:
    """
    Calls LLM with retry logic and enforces strict JSON schema via Pydantic.
    """
    for attempt in range(MAX_RETRIES):
        try:
            response = await client.chat.completions.create(
                model=OPENAI_MODEL,
                messages=[{"role": "system", "content": prompt}],
                response_format={"type": "json_object"} # Enforce JSON mode
            )
            
            raw_content = response.choices[0].message.content or "{}"
            
            # Validate output against the expected Pydantic model
            validated_data = response_model.model_validate_json(raw_content)
            return validated_data

        except ValidationError as ve:
            logger.warning(f"[Retry {attempt+1}] Pydantic Validation Error: {ve}")
        except Exception as e:
            logger.warning(f"[Retry {attempt+1}] LLM API Error: {str(e)}")

        await asyncio.sleep(2 ** attempt)  # Exponential backoff

    logger.error("LLM failed after maximum retries.")
    return {"error": "LLM failed to produce valid output"}


# ==========================================
# 📐 CAD FILE SUPPORT (DXF/DWG)
# ==========================================
def extract_text_from_cad(file_path: str) -> str:
    """Extracts text entities from DXF files."""
    try:
        import ezdxf
        doc = ezdxf.readfile(file_path)  # type: ignore
        msp = doc.modelspace()
        
        texts = [
            entity.text if hasattr(entity, "text") else entity.plain_text()  # type: ignore
            for entity in msp 
            if entity.dxftype() in ["TEXT", "MTEXT"]
        ]
        return "\n".join(texts)
    except ImportError:
        logger.error("ezdxf is not installed. Run: pip install ezdxf")
        return ""
    except Exception as e:
        logger.error(f"CAD Extraction Error: {e}")
        return ""


# ==========================================
# 🤖 MULTI-AGENT SEQUENTIAL PIPELINE
# ==========================================
async def document_agent(raw_text: str) -> DocOutput | dict:
    prompt = f"""
    You are a Document Analysis Agent. Clean and structure the following RFQ text.
    Return a JSON object with 'project_type', 'key_requirements' (list), and 'clean_text'.
    Raw Text: {raw_text[:4000]} 
    """
    return await safe_structured_llm_call(prompt, DocOutput) # type: ignore

async def boq_agent(clean_text: str) -> BOQOutput | dict:
    prompt = f"""
    Extract BOQ items from the text. 
    Return a JSON object with a 'boq_items' list, each containing 'item', 'quantity' (number), and 'unit'.
    
    CRITICAL INSTRUCTION: The 'quantity' field MUST be a valid number (float). 
    If the quantity is missing, or listed as a word like "various" or "multiple", you MUST output 0.0. 
    Do not output null, None, or strings for the quantity field.
    
    Text: {clean_text[:4000]}
    """
    return await safe_structured_llm_call(prompt, BOQOutput) # type: ignore


async def risk_agent(clean_text: str, boq_data: str) -> RiskOutput | dict:
    prompt = f"""
    Analyze the RFQ for risks.
    Return a JSON object with 'risks' (list of strings) and 'risk_level' ("Low", "Medium", "High").
    RFQ Text: {clean_text[:2000]}
    BOQ Data: {boq_data}
    """
    return await safe_structured_llm_call(prompt, RiskOutput) # type: ignore

async def summary_agent(doc_data: str, boq_data: str, risk_data: str) -> SummaryOutput | dict:
    prompt = f"""
    Generate an Executive Summary for the project.
    Return a JSON object with 'summary' (string) and 'key_points' (list of strings).
    Doc Data: {doc_data}
    BOQ Data: {boq_data}
    Risk Data: {risk_data}
    """
    return await safe_structured_llm_call(prompt, SummaryOutput) # type: ignore

async def run_sequential_pipeline(file_path: str) -> dict:
    """Coordinator Agent: Manages the execution of specialist agents."""
    logger.info(f"Starting sequential pipeline for: {file_path}")
    path_obj = Path(file_path)

    # 1. File Handling
    ext = path_obj.suffix.lower()
    
    if ext in [".dxf", ".dwg"]:
        raw_text = extract_text_from_cad(file_path)
        
    elif ext == ".pdf":
        from app.services.pdf_service import extract_pdf
        raw_text = str(extract_pdf(file_path))
        
    elif ext == ".docx":
        from app.services.docx_service import extract_docx
        raw_text = str(extract_docx(file_path))
        
    elif ext in [".xlsx", ".xls"]:
        from app.services.excel_service import extract_boq_data
        # Extract the BOQ rows and convert them to a readable string format for the Agent
        boq_data = extract_boq_data(file_path)
        raw_text = "\n".join([str(row) for row in boq_data]) if boq_data else ""
        
    else:
        # Fallback for .txt or .csv files, with a safety net for Windows encoding
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="windows-1252", errors="ignore") as f:
                raw_text = f.read()

    if not raw_text or len(raw_text.strip()) < 10:
        return {"error": f"Failed to extract readable text from {path_obj.name}."}

    # 1. File Handling
    ext = path_obj.suffix.lower()
    
    if ext in [".dxf", ".dwg"]:
        raw_text = extract_text_from_cad(file_path)
        
    elif ext == ".pdf":
        from app.services.pdf_service import extract_pdf
        raw_text = str(extract_pdf(file_path))
        
    elif ext == ".docx":
        from app.services.docx_service import extract_docx
        raw_text = str(extract_docx(file_path))
        
    elif ext in [".xlsx", ".xls"]:
        from app.services.excel_service import extract_boq_data
        # Extract the BOQ rows and convert them to a readable string format for the Agent
        boq_data = extract_boq_data(file_path)
        raw_text = "\n".join([str(row) for row in boq_data]) if boq_data else ""
        
    else:
        # Fallback for .txt or .csv files, with a safety net for Windows encoding
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                raw_text = f.read()
            
        except UnicodeDecodeError:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                raw_text = f.read()

    if not raw_text or len(raw_text.strip()) < 10:
        return {"error": f"Failed to extract readable text from {path_obj.name}."} 

    # 2. Sequential Execution with type casting
    doc = await document_agent(raw_text)
    if isinstance(doc, dict) and "error" in doc: return doc
    doc = cast(DocOutput, doc)

    boq = await boq_agent(doc.clean_text)
    if isinstance(boq, dict) and "error" in boq: return boq
    boq = cast(BOQOutput, boq)

    risk = await risk_agent(doc.clean_text, boq.model_dump_json())
    if isinstance(risk, dict) and "error" in risk: return risk
    risk = cast(RiskOutput, risk)

    summary = await summary_agent(doc.model_dump_json(), boq.model_dump_json(), risk.model_dump_json())
    if isinstance(summary, dict) and "error" in summary: return summary
    summary = cast(SummaryOutput, summary)

    # 3. Final Output Assembly
    return {
        "document": doc.model_dump(),
        "boq": boq.model_dump(),
        "risk": risk.model_dump(),
        "summary": summary.model_dump()
    }


# ==========================================
# 🛠️ LOCAL AGENT TOOLS (For Dynamic Loop)
# ==========================================
async def calculate_totals(items: list) -> str:
    """Tool: Calculates the sum of item quantities."""
    logger.info("🛠️ Tool Executed: calculate_totals")
    try:
        df = pd.DataFrame(items)
        if 'quantity' not in df.columns:
            return "Error: Could not find 'quantity' key in provided items."
        df['quantity'] = pd.to_numeric(df['quantity'], errors='coerce').fillna(0)
        return f"Calculated total quantity: {df['quantity'].sum()}"
    except Exception as e:
        logger.error(f"❌ Calculate tool failed: {e}")
        return f"Error: {str(e)}"

async def extract_table(document_name: str) -> str:
    """Extracts tabular data safely using standard pathlib."""
    logger.info(f"🛠️ Tool Executed: extract_table | Target: {document_name}")
    
    clean_search_name = Path(document_name).stem.lower()
    target_file = None

    if UPLOAD_PATH.exists() and UPLOAD_PATH.is_dir():
        for file in UPLOAD_PATH.iterdir():
            if file.is_file() and clean_search_name in file.stem.lower():
                target_file = file
                break

    if not target_file:
        return f"No matching file found for: {document_name}"

    if target_file.suffix.lower() in ['.xlsx', '.xls', '.csv']:
        try:
            df = pd.read_csv(target_file) if target_file.suffix.lower() == '.csv' else pd.read_excel(target_file)
            return f"Raw Data:\n```csv\n{df.to_csv(index=False)}\n```"
        except Exception as e:
            return f"Error reading {target_file.name}: {str(e)}"
    
    return f"File '{target_file.name}' is not a tabular format (.csv/.xlsx)."


# ==========================================
# 🤖 DYNAMIC AGENT REASONING LOOP (ReAct)
# ==========================================
async def run_agent_loop(user_command: str) -> str:
    """Interactive agent loop utilizing configured tools."""
    
    # Check available files
    available_files = [f.name for f in UPLOAD_PATH.iterdir() if f.is_file()] if UPLOAD_PATH.exists() else []
    file_list_str = ", ".join(available_files) if available_files else "No files found."

    tools = [
        {
            "type": "function",
            "function": {
                "name": "calculate_totals",
                "description": "Calculates the sum total of item quantities.",
                "parameters": {
                    "type": "object", 
                    "properties": {"items": {"type": "array", "items": {"type": "object"}}}, 
                    "required": ["items"]
                }
            }
        },
        {
            "type": "function",
            "function": {
                "name": "extract_table",
                "description": "Extracts tabular BOQ/BOM data from a specified file.",
                "parameters": {
                    "type": "object", 
                    "properties": {"document_name": {"type": "string"}}, 
                    "required": ["document_name"]
                }
            }
        }
        # Add search_documents here when app.pipeline is ready
    ]

    messages = [
        {"role": "system", "content": (
            "You are an analytical Engineering Assistant.\n"
            f"Available files: [{file_list_str}].\n"
            "Use tools to extract data or calculate totals. Provide direct, concise answers."
        )},
        {"role": "user", "content": user_command}
    ]

    while True:
        response = await client.chat.completions.create(
            model=OPENAI_MODEL, 
            messages=cast(Any, messages), 
            tools=cast(Any, tools), 
            tool_choice="auto"
        )
        msg = response.choices[0].message
        
        # 🐛 FIX 2: Safe dictionary construction to prevent API crashes on tool calls
        assistant_msg = {"role": msg.role, "content": msg.content or ""}
        
        if msg.tool_calls:
            assistant_msg["tool_calls"] = [ # type: ignore
                {
                    "id": t.id, 
                    "type": t.type, 
                    "function": {"name": t.function.name, "arguments": t.function.arguments} # type: ignore
                } 
                for t in msg.tool_calls
            ]
            
        messages.append(assistant_msg)

        if not msg.tool_calls:
            return msg.content or "No response generated."

        for tool_call in msg.tool_calls:
            name = tool_call.function.name # type: ignore
            try:
                args = json.loads(tool_call.function.arguments) # type: ignore
            except json.JSONDecodeError:
                args = {}

            logger.info(f"Executing: {name} | Args: {args}")

            # Tool Router
            if name == "calculate_totals":
                result = await calculate_totals(args.get('items', []))
            elif name == "extract_table":
                result = await extract_table(args.get('document_name', ''))
            else:
                result = "Error: Tool not found."

            messages.append({
                "tool_call_id": tool_call.id,
                "role": "tool",
                "name": name,
                "content": str(result)
            })