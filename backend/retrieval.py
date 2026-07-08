import os
import re
import requests
import chromadb
import numpy as np
from rank_bm25 import BM25Okapi
from typing import List, Dict, Any, Tuple

# Initialize ChromaDB persistent client
DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "chroma_db")
os.makedirs(os.path.dirname(DB_PATH), exist_ok=True)
chroma_client = chromadb.PersistentClient(path=DB_PATH)
collection = chroma_client.get_or_create_collection(name="tender_child_chunks")

# Global dict to store BM25 indexes per doc_id or active session
# Key: doc_id, Value: {"bm25": BM25Okapi, "chunks": list_of_child_chunks}
bm25_store: Dict[str, Dict[str, Any]] = {}

def get_embedding(text: str, model: str = "nomic-embed-text") -> List[float]:
    """
    Get text embedding from local Ollama instance.
    """
    try:
        response = requests.post(
            "http://localhost:11434/api/embeddings",
            json={"model": model, "prompt": text},
            timeout=10
        )
        response.raise_for_status()
        return response.json()["embedding"]
    except Exception as e:
        print(f"Error fetching embedding from Ollama: {e}")
        # Fallback to a zero vector if Ollama fails (to prevent crash)
        return [0.0] * 768

def tokenize(text: str) -> List[str]:
    """
    Tokenizes text for BM25. Preserves alphanumeric codes.
    """
    return re.findall(r'\b\w+\b', text.lower())

def index_document_chunks(doc_id: str, parent_chunks: List[Dict], child_chunks: List[Dict]):
    """
    Indexes child chunks in ChromaDB and sets up a BM25 index for the document.
    """
    if not child_chunks:
        return
        
    ids = []
    embeddings = []
    metadatas = []
    documents = []
    
    # Store parent chunks in memory or a database. 
    # For now, let's include the full parent text directly in the child's metadata 
    # so we don't need a separate database for parents!
    parent_map = {p["id"]: p["text"] for p in parent_chunks}
    
    print(f"Embedding {len(child_chunks)} chunks for {doc_id}...")
    for chunk in child_chunks:
        parent_text = parent_map.get(chunk["parent_id"], "")
        
        # Metadata must only contain simple types (string, int, float, bool)
        metadata = {
            "doc_id": doc_id,
            "parent_id": chunk["parent_id"],
            "parent_text": parent_text,
            "filename": chunk["filename"],
            "pages": ",".join(map(str, chunk["pages"])) # Convert list to comma-separated string
        }
        
        vector = get_embedding(chunk["text"])
        
        ids.append(chunk["id"])
        embeddings.append(vector)
        metadatas.append(metadata)
        documents.append(chunk["text"])
        
    # Add to ChromaDB
    collection.add(
        ids=ids,
        embeddings=embeddings,
        metadatas=metadatas,
        documents=documents
    )
    
    # Initialize BM25 for this document
    corpus = [chunk["text"] for chunk in child_chunks]
    tokenized_corpus = [tokenize(doc) for doc in corpus]
    bm25 = BM25Okapi(tokenized_corpus)
    
    bm25_store[doc_id] = {
        "bm25": bm25,
        "chunks": child_chunks,
        "parent_map": parent_map
    }
    print(f"Indexed document {doc_id} in Vector DB and BM25.")

def clear_document_index(doc_id: str):
    """
    Removes a document's indexes from both ChromaDB and BM25 store.
    """
    try:
        collection.delete(where={"doc_id": doc_id})
    except Exception as e:
        print(f"Error deleting from ChromaDB: {e}")
        
    if doc_id in bm25_store:
        del bm25_store[doc_id]

def hybrid_search(doc_id: Any, query: str, top_k: int = 5, rrf_k: int = 60) -> List[Dict[str, Any]]:
    """
    Performs hybrid search (BM25 + Vector Search) and merges results using Reciprocal Rank Fusion (RRF).
    Supports single doc_id (str) or multiple doc_ids (List[str]).
    """
    from typing import Union
    doc_ids = [doc_id] if isinstance(doc_id, str) else doc_id
    
    # 1. Vector Search
    query_vector = get_embedding(query)
    
    vector_results = []
    try:
        # Build ChromaDB filter
        if len(doc_ids) == 1:
            where_filter = {"doc_id": doc_ids[0]}
        else:
            where_filter = {"doc_id": {"$in": doc_ids}}
            
        results = collection.query(
            query_embeddings=[query_vector],
            n_results=top_k * 2, # Fetch more to allow good fusion
            where=where_filter
        )
        
        if results and results["ids"] and results["ids"][0]:
            for idx in range(len(results["ids"][0])):
                # Reconstruct chunk details
                vector_results.append({
                    "id": results["ids"][0][idx],
                    "text": results["documents"][0][idx],
                    "parent_id": results["metadatas"][0][idx]["parent_id"],
                    "parent_text": results["metadatas"][0][idx]["parent_text"],
                    "filename": results["metadatas"][0][idx]["filename"],
                    "pages": [int(x) for x in results["metadatas"][0][idx]["pages"].split(",") if x]
                })
    except Exception as e:
        print(f"ChromaDB query error: {e}")
        
    # 2. BM25 Search
    bm25_results = []
    all_bm25_candidates = []
    
    for d_id in doc_ids:
        if d_id in bm25_store:
            store = bm25_store[d_id]
            bm25 = store["bm25"]
            chunks = store["chunks"]
            parent_map = store["parent_map"]
            
            tokenized_query = tokenize(query)
            scores = bm25.get_scores(tokenized_query)
            
            for idx, score in enumerate(scores):
                if score <= 0:
                    continue
                chunk = chunks[idx]
                all_bm25_candidates.append({
                    "score": score,
                    "item": {
                        "id": chunk["id"],
                        "text": chunk["text"],
                        "parent_id": chunk["parent_id"],
                        "parent_text": parent_map.get(chunk["parent_id"], ""),
                        "filename": chunk["filename"],
                        "pages": chunk["pages"]
                    }
                })
                
    # Sort all candidates across all documents by BM25 score
    all_bm25_candidates.sort(key=lambda x: x["score"], reverse=True)
    bm25_results = [c["item"] for c in all_bm25_candidates[:top_k * 2]]
            
    # 3. Reciprocal Rank Fusion (RRF)
    # RRF maps: chunk_id -> rrf_score
    rrf_scores = {}
    chunk_lookup = {}
    
    # helper to update RRF score
    def update_rrf_score(results_list):
        for rank, item in enumerate(results_list):
            chunk_id = item["id"]
            chunk_lookup[chunk_id] = item
            # rank is 0-indexed, so rank+1 is the actual rank
            score = 1.0 / (rrf_k + (rank + 1))
            rrf_scores[chunk_id] = rrf_scores.get(chunk_id, 0.0) + score

    update_rrf_score(vector_results)
    update_rrf_score(bm25_results)
    
    # If both lists are empty, fallback to basic search in ChromaDB
    if not rrf_scores and vector_results:
        # Fallback to whatever vector search found
        return vector_results[:top_k]
    elif not rrf_scores:
        return []
        
    # Sort by RRF score descending
    sorted_chunk_ids = sorted(rrf_scores.keys(), key=lambda x: rrf_scores[x], reverse=True)
    
    # Return top_k merged results
    merged_results = [chunk_lookup[cid] for cid in sorted_chunk_ids[:top_k]]
    
    return merged_results
