"""
Agent Pipeline Orchestrator
app/pipeline/agent_pipeline.py

This module bridges the FastAPI routers with the core AI services. 
It combines the RAG ingestion process with the Multi-Agent analysis workflows,
and defines standard tools for the LLM agents to use.
"""

import os
import logging
from typing import Dict, Any, List, Optional

# Import the refactored agent services
from app.brain.agent_service import run_sequential_pipeline, run_agent_loop

# Import the document ingestion pipeline
from app.brain.document_service import process_document 

# Import retrieval service for the agent's search tool
from app.pipeline.optimization_service import retrieve_and_rerank 

logger = logging.getLogger(__name__)

# ==========================================
# 🚀 END-TO-END RFQ ANALYSIS PIPELINE
# ==========================================
async def run_full_rfq_analysis(file_path: str) -> Dict[str, Any]:
    """
    Executes the complete pipeline for a newly uploaded RFQ document.
    
    Workflow:
    1. Ingests the document into the Vector DB (RAG prep).
    2. Runs the Sequential Multi-Agent pipeline (Doc -> BOQ -> Risk -> Summary).
    
    Args:
        file_path (str): The absolute or relative path to the uploaded document.
        
    Returns:
        Dict[str, Any]: The structured JSON output from the multi-agent pipeline.
    """
    logger.info(f"🚀 Initiating Full RFQ Pipeline for: {file_path}")
    
    # STEP 1: RAG Ingestion (Chunking, Embedding, Vector Storage)
    try:
        logger.info("Phase 1: Starting Document Ingestion for RAG...")
        # This makes the document searchable via tools later
        await process_document(file_path)
        logger.info("Phase 1 Complete: Document successfully indexed in Vector Store.")
    except Exception as e:
        # We log the error but do not hard-fail, allowing the direct agent analysis to still attempt execution
        logger.error(f"Phase 1 Error (Vector Ingestion Failed): {str(e)}")
        logger.warning("Proceeding to Phase 2 without Vector DB indexing.")

    # STEP 2: Multi-Agent Sequential Analysis
    try:
        logger.info("Phase 2: Executing Multi-Agent Sequential Analysis...")
        analysis_results = await run_sequential_pipeline(file_path)
        
        # Check if the pipeline returned an error dict
        if "error" in analysis_results:
            logger.error(f"Phase 2 Failed during agent execution: {analysis_results['error']}")
            return {"status": "error", "message": analysis_results["error"]}
            
        logger.info("Phase 2 Complete: Multi-Agent Analysis successful.")
        
        # Wrap the successful results in a standardized API response format
        return {
            "status": "success",
            "data": analysis_results
        }

    except Exception as e:
        logger.error(f"❌ Pipeline encountered a critical failure: {str(e)}", exc_info=True)
        return {
            "status": "error", 
            "message": f"Critical pipeline failure: {str(e)}"
        }


# ==========================================
# 💬 INTERACTIVE AGENT CHAT PIPELINE
# ==========================================
async def execute_agentic_chat(user_command: str) -> Dict[str, Any]:
    """
    Handles interactive Q&A using the dynamic ReAct agent loop.
    Allows the user to query the system, utilizing tools like calculate_totals
    or extract_table based on the available documents.
    
    Args:
        user_command (str): The prompt or question from the user.
        
    Returns:
        Dict[str, Any]: The agent's text response.
    """
    logger.info(f"💬 Incoming Agent Chat Request: {user_command}")
    
    if not user_command or not user_command.strip():
        return {
            "status": "error",
            "response": "User command cannot be empty."
        }

    try:
        # Trigger the dynamic tool-calling loop from agent_services.py
        response = await run_agent_loop(user_command)
        
        logger.info("Agent Chat Request completed successfully.")
        return {
            "status": "success",
            "response": response
        }
        
    except Exception as e:
        logger.error(f"❌ Agent Loop failed: {str(e)}", exc_info=True)
        return {
            "status": "error",
            "response": f"The assistant encountered an error: {str(e)}"
        }


# ==========================================================
# 🛠️ AGENT TOOL: search_documents
# ==========================================================
async def search_documents(query: str) -> str:
    """
    Tool: Agent search with deep retrieval and reranking.
    Provides context-rich chunks back to the reasoning agent.
    """
    query = query.strip()
    if not query:
        return "Error: Search query cannot be empty."

    logger.info(f"🛠️ Tool Execution: search_documents | Query: '{query}'")
    
    try:
        # Fetch wider initial net (40) for the reranker to distill to top 10
        results, _ = await retrieve_and_rerank(query=query, initial_k=40, final_k=10)
        
        if not results:
            return f"No relevant documents found for the query: '{query}'."
                
        # Format output with Markdown headers so the LLM agent can easily parse sources
        context_blocks = []
        for index, r in enumerate(results, start=1):
            metadata = r.get("metadata", {})
            source_path = str(metadata.get("source", "Unknown_Source"))
            source_name = os.path.basename(source_path)
            
            text_content = r.get("text", "").strip() or "[No readable text extracted]"
            
            # Markdown structuring helps the Agent separate context visually
            context_blocks.append(f"### Source {index}: {source_name}\n{text_content}\n")
            
        return "\n".join(context_blocks)
        
    except Exception as e:
        logger.error(f"❌ Search tool execution failed: {str(e)}", exc_info=True)
        return f"Error executing document search. System encountered an issue: {str(e)}"


# ==========================================================
# 🏗️ HELPER: Standardized Response Builder
# ==========================================================
def _build_response(
    question: str, 
    answer: str, 
    sources: Optional[List[str]] = None, 
    chunks_used: int = 0, 
    confidence: float = 0.0, 
    context: str = "",
    error: Optional[str] = None
) -> Dict[str, Any]:
    """
    Constructs a standardized, API-ready dictionary for the frontend or next pipeline stage.
    """
    # Create a safe, truncated preview of the context for logging/debugging
    preview_limit = 500
    context_preview = context if len(context) <= preview_limit else f"{context[:preview_limit]}... [Truncated]"
    
    response_payload = {
        "question": question.strip(),
        "answer": answer.strip(),
        # Deduplicate sources so the API response doesn't list the same file 10 times
        "sources": sorted(list(set(sources))) if sources else [], 
        "chunks_used": max(0, chunks_used), # Ensure non-negative
        "confidence": round(confidence, 2), # Round to 2 decimals for clean JSON
        "context_preview": context_preview
    }
    
    if error:
        response_payload["error"] = error.strip()
        
    return response_payload