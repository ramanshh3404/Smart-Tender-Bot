import os
import sys

# Ensure backend folder is in path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.chunking import create_parent_child_chunks
from backend.retrieval import index_document_chunks, hybrid_search, clear_document_index

def main():
    print("=== RAG Core Verification ===")
    
    current_dir = os.path.dirname(os.path.abspath(__file__))
    tender_pdf = os.path.join(current_dir, "data", "samples", "ongc_tender_pipeline.pdf")
    proposal_pdf = os.path.join(current_dir, "data", "samples", "vendor_bid_proposal.pdf")
    
    if not os.path.exists(tender_pdf) or not os.path.exists(proposal_pdf):
        print("Error: Sample PDFs not found! Run create_sample_pdfs.py first.")
        return
        
    tender_id = "test_tender_doc"
    proposal_id = "test_proposal_doc"
    
    # 1. Test Chunking
    print("\n1. Testing Parent-Child Chunking on Tender PDF...")
    t_parents, t_children = create_parent_child_chunks(tender_pdf, tender_id)
    print(f"Generated {len(t_parents)} parent chunks and {len(t_children)} child chunks.")
    
    print("\nTesting Parent-Child Chunking on Proposal PDF...")
    p_parents, p_children = create_parent_child_chunks(proposal_pdf, proposal_id)
    print(f"Generated {len(p_parents)} parent chunks and {len(p_children)} child chunks.")
    
    # 2. Test Indexing
    print("\n2. Testing indexing...")
    # Clear previous indexes if any
    clear_document_index(tender_id)
    clear_document_index(proposal_id)
    
    # Index
    index_document_chunks(tender_id, t_parents, t_children)
    index_document_chunks(proposal_id, p_parents, p_children)
    
    # 3. Test Hybrid Search
    print("\n3. Testing Hybrid Search (BM25 + ChromaDB Vector RRF)...")
    queries = [
        "pipeline grade API 5L",
        "hydrostatic testing pressure test hours",
        "ISO 9001 and API Spec Q1 certificates"
    ]
    
    for query in queries:
        print(f"\nQuery: '{query}'")
        results = hybrid_search(proposal_id, query, top_k=2)
        print(f"Found {len(results)} matches in proposal:")
        for idx, r in enumerate(results):
            print(f"  [{idx + 1}] Child Text: {r['text']}")
            print(f"      Parent ID: {r['parent_id']}")
            print(f"      Page references: {r['pages']}")
            print(f"      Parent Context snippet: {r['parent_text'][:120]}...")
            
    print("\n=== Verification Completed ===")

if __name__ == "__main__":
    main()
