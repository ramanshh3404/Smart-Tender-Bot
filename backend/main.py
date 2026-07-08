import os
import shutil
import uuid
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List, Union, Any

from backend.chunking import create_parent_child_chunks
from backend.retrieval import index_document_chunks, clear_document_index, hybrid_search
from backend.comparison import run_full_comparison, query_llm
from backend.judge import log_chat, log_feedback, get_analytics_summary

app = FastAPI(title="Procurement & Vendor Query Analyzer API")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], # In production, restrict this to your frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)

class CompareRequest(BaseModel):
    tender_doc_id: str
    proposal_doc_id: str

class ChatRequest(BaseModel):
    doc_id: Union[str, List[str]]
    session_id: str
    query: str

class FeedbackRequest(BaseModel):
    chat_id: int
    value: int # 1 for upvote, -1 for downvote

@app.get("/api/health")
def health_check():
    return {"status": "healthy", "service": "tender-analyzer-backend"}

@app.post("/api/upload")
async def upload_file(
    file: UploadFile = File(...),
    doc_type: str = Form(...) # "tender" or "proposal"
):
    """
    Uploads a PDF file, parses it, runs Parent-Child chunking, and indexes it.
    """
    if not file.filename.endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
        
    doc_id = f"{doc_type}_{uuid.uuid4().hex[:8]}"
    file_path = os.path.join(UPLOAD_DIR, f"{doc_id}_{file.filename}")
    
    # Save file
    try:
        with open(file_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save file: {str(e)}")
        
    # Clear index first if it already exists (safety)
    clear_document_index(doc_id)
    
    # Create chunks and index
    try:
        print(f"Processing upload for {file.filename} as {doc_type}...")
        parent_chunks, child_chunks = create_parent_child_chunks(file_path, doc_id)
        
        if not parent_chunks:
            raise HTTPException(status_code=400, detail="Could not extract text from the PDF.")
            
        index_document_chunks(doc_id, parent_chunks, child_chunks)
        
        return {
            "success": True,
            "doc_id": doc_id,
            "filename": file.filename,
            "type": doc_type,
            "num_parent_chunks": len(parent_chunks),
            "num_child_chunks": len(child_chunks)
        }
    except Exception as e:
        # Clean up file on failure
        if os.path.exists(file_path):
            os.remove(file_path)
        print(f"Error processing document: {e}")
        raise HTTPException(status_code=500, detail=f"Error indexing document: {str(e)}")

@app.post("/api/compare")
async def compare_documents(request: CompareRequest):
    """
    Runs the tender specification compliance comparison against the vendor proposal.
    """
    try:
        results = run_full_comparison(request.tender_doc_id, request.proposal_doc_id)
        return {
            "success": True,
            "results": results
        }
    except Exception as e:
        print(f"Error comparing documents: {e}")
        raise HTTPException(status_code=500, detail=f"Error running comparison: {str(e)}")

@app.post("/api/chat")
async def chat_document(request: ChatRequest):
    """
    Chat endpoint using Balanced Hybrid Search (Tender + Proposal balancing) and Parent-Child retrieval.
    """
    try:
        # Normalize doc_ids into a manageable list structure
        input_ids = [request.doc_id] if isinstance(request.doc_id, str) else request.doc_id
        
        # Segment the document identifiers based on their dynamic prefixes
        tender_ids = [d for d in input_ids if d.startswith("tender")]
        proposal_ids = [d for d in input_ids if d.startswith("proposal")]
        
        search_results = []
        
        # Balanced Ingestion: Run distinct search tasks to prevent context starvation
        if tender_ids and proposal_ids:
            # Multi-document setup: pull evenly from both document classes
            search_results.extend(hybrid_search(tender_ids, request.query, top_k=2))
            search_results.extend(hybrid_search(proposal_ids, request.query, top_k=2))
        else:
            # Fallback for single-file queries
            search_results = hybrid_search(input_ids, request.query, top_k=4)
        
        # Extract and deduplicate parent text for context wrapping
        seen_parents = set()
        context_parts = []
        references = []
        
        for r in search_results:
            p_id = r["parent_id"]
            if p_id not in seen_parents:
                seen_parents.add(p_id)
                context_parts.append(r["parent_text"])
                
            references.append({
                "chunk_id": r["id"],
                "filename": r["filename"],
                "pages": r["pages"],
                "text": r["text"]  # Child text snippet
            })
            
        context = "\n\n".join(context_parts)
        
        # Prompt Ollama with balanced contextual parameters
        prompt = f"""
        You are an ONGC Technical Compliance Assistant reviewing procurement documents.
        Analyze the provided context to answer the user's inquiry accurately.
        
        Compare the specifications or data points between the tender documents and vendor proposals if both are present in the context.
        If the context does not contain the answer, state that you cannot find it in the provided documents.
        Be precise, clear, and explicitly mention specification codes, metrics, or numbers.
        
        [CONTEXT]
        {context if context else "No relevant context found in documents."}
        
        [USER QUERY]
        {request.query}
        """
        
        system_prompt = "You are a professional compliance assistant. Answer queries strictly using cross-document comparison data from the provided context."
        
        response = query_llm(prompt, system_prompt, model="qwen2.5:7b")
        if not response:
            response = query_llm(prompt, system_prompt, model="llama3.2:latest")
            
        if not response:
            response = "I encountered an error querying the local model. Please verify Ollama is running."
            
        # Log interaction parameters to the SQLite tracking database
        chat_id = log_chat(
            session_id=request.session_id,
            query=request.query,
            response=response,
            context=context
        )
        
        return {
            "success": True,
            "chat_id": chat_id,
            "response": response,
            "references": references
        }
    except Exception as e:
        print(f"Chat execution error: {e}")
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")

@app.post("/api/feedback")
async def log_chat_feedback(request: FeedbackRequest):
    """
    Submits feedback (upvote/downvote) for a specific chat message.
    """
    try:
        log_feedback(request.chat_id, request.value)
        return {"success": True, "detail": "Feedback saved."}
    except Exception as e:
        print(f"Feedback error: {e}")
        raise HTTPException(status_code=500, detail=f"Feedback log error: {str(e)}")

@app.get("/api/analytics")
async def get_analytics():
    """
    Returns analytics summary (chats, votes, failure types, audit logs).
    """
    try:
        summary = get_analytics_summary()
        return {
            "success": True,
            "data": summary
        }
    except Exception as e:
        print(f"Analytics query error: {e}")
        raise HTTPException(status_code=500, detail=f"Error compiling analytics: {str(e)}")