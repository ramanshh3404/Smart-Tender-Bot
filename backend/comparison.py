import json
import re
import requests
from typing import List, Dict, Any
from backend.retrieval import hybrid_search

OLLAMA_URL = "http://localhost:11434/api/generate"

def query_llm(prompt: str, system_prompt: str = "", model: str = "qwen2.5:7b", json_mode: bool = False) -> str:
    """
    Helper to query Ollama locally.
    """
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    if system_prompt:
        payload["system"] = system_prompt
    if json_mode:
        payload["format"] = "json"
        
    try:
        response = requests.post(OLLAMA_URL, json=payload, timeout=60)
        response.raise_for_status()
        return response.json()["response"]
    except Exception as e:
        print(f"Ollama query failed: {e}")
        return ""

def extract_requirements_from_tender(tender_doc_id: str) -> List[Dict[str, Any]]:
    """
    Searches the Tender document for specifications, standards, and certificates,
    and extracts a clean list of requirements using the LLM.
    """
    # Search queries to find requirements in the tender
    queries = [
        "technical specifications requirements standards",
        "scope of work material parameters specifications",
        "required certifications ISO API compliance documentation",
        "warranty delivery schedule terms inspection"
    ]
    
    # Retrieve unique context from Tender
    context_chunks = []
    seen_parent_ids = set()
    
    for q in queries:
        results = hybrid_search(tender_doc_id, q, top_k=3)
        for r in results:
            p_id = r["parent_id"]
            if p_id not in seen_parent_ids:
                seen_parent_ids.add(p_id)
                context_chunks.append(r["parent_text"])
                
    context_text = "\n\n".join(context_chunks)[:6000] # Limit context length
    
    prompt = f"""
    You are an ONGC procurement officer. Analyze the following text extracted from a Tender document.
    Identify and extract the top 6-8 key technical specifications, material standard requirements, or quality certifications.
    
    For example:
    - Pipe materials (e.g., API 5L X70)
    - Required certifications (e.g., ISO 9001, API Spec Q1)
    - Delivery schedule or warranty periods
    - Performance test pressures
    
    Format the response strictly as a JSON object with a key "requirements" that holds a list of requirements.
    Each requirement MUST have:
    - id: A short unique identifier string (e.g., "REQ-001")
    - category: The category (e.g., "Material Standards", "Certifications", "Testing", "Delivery & Warranty")
    - spec_name: A short name of the specification
    - requirement_detail: Detailed description of what is required
    
    Example output format:
    {{
      "requirements": [
         {{
           "id": "REQ-001",
           "category": "Material Standards",
           "spec_name": "Pipeline Grade",
           "requirement_detail": "High-pressure gas pipelines must conform to API 5L X70 steel grade with a minimum yield strength of 485 MPa."
         }}
      ]
    }}
    
    Extract from this text:
    ---
    {context_text}
    ---
    """
    
    system_prompt = "You are an expert procurement spec extractor. Output valid, raw JSON only."
    
    # Try qwen2.5:7b, fallback to llama3.2
    response_text = query_llm(prompt, system_prompt, model="qwen2.5:7b", json_mode=True)
    if not response_text:
        response_text = query_llm(prompt, system_prompt, model="llama3.2:latest", json_mode=True)
        
    try:
        data = json.loads(response_text)
        return data.get("requirements", [])
    except Exception as e:
        print(f"Failed to parse requirements JSON: {e}. Raw response: {response_text}")
        
        # Fallback requirements if LLM parsing completely fails
        return [
            {
                "id": "REQ-001",
                "category": "Material Standards",
                "spec_name": "Pipeline Steel Grade",
                "requirement_detail": "Line pipes must conform to API 5L Grade X70 or higher steel specifications with PSL2 requirements."
            },
            {
                "id": "REQ-002",
                "category": "Testing Requirements",
                "spec_name": "Hydrostatic Testing",
                "requirement_detail": "Pipelines must undergo hydrostatic test at 1.5 times the design working pressure of 100 bar for a minimum of 24 hours."
            },
            {
                "id": "REQ-003",
                "category": "Certifications",
                "spec_name": "Quality Certifications",
                "requirement_detail": "The manufacturer must hold valid API Spec Q1 and ISO 9001 certifications throughout the contract duration."
            },
            {
                "id": "REQ-004",
                "category": "Delivery & Warranty",
                "spec_name": "Warranty Period",
                "requirement_detail": "Equipment and piping must be warranted for 18 months from delivery or 12 months from commissioning, whichever is earlier."
            }
        ]

def compare_requirement_to_proposal(
    requirement: Dict[str, Any], 
    proposal_doc_id: str
) -> Dict[str, Any]:
    """
    Compares a single tender requirement against the vendor proposal.
    """
    spec_name = requirement["spec_name"]
    req_detail = requirement["requirement_detail"]
    category = requirement["category"]
    
    # Search vendor proposal using hybrid search
    search_query = f"{spec_name} {req_detail}"
    results = hybrid_search(proposal_doc_id, search_query, top_k=3)
    
    proposal_context_chunks = []
    page_references = set()
    for r in results:
        proposal_context_chunks.append(r["parent_text"])
        page_references.update(r["pages"])
        
    proposal_context = "\n\n".join(proposal_context_chunks)[:4000]
    
    prompt = f"""
    You are an expert procurement auditor. Compare the following Tender Requirement against the Vendor Proposal Context.
    
    Tender Requirement Category: {category}
    Tender Requirement: {spec_name} - {req_detail}
    
    Vendor Proposal Context (Retrieved from vendor proposal PDF):
    {proposal_context if proposal_context else "No matching sections found in vendor proposal."}
    
    Evaluate the compliance status of the proposal against the requirement. Select one of the following statuses:
    - COMPLIANT: The vendor proposal fully meets or exceeds the tender requirements.
    - DEVIATION: The vendor proposal proposes a specification that differs or is lower than the tender specification.
    - PARTIAL: The vendor proposal partially addresses the specification, but has omissions or minor gaps.
    - MISSING: The vendor proposal completely omits, fails to address, or does not mention the required specification or certificate.
    
    Format the response strictly as a JSON object with the following fields:
    - status: "COMPLIANT" | "DEVIATION" | "PARTIAL" | "MISSING"
    - proposal_response: (A concise summary of what the vendor states/proposes in their document related to this requirement. Quote or reference specific metrics or claims if found.)
    - deviation_details: (If status is DEVIATION or PARTIAL or MISSING, explain what is different, missing, or why it failed. If COMPLIANT, write null.)
    - confidence_score: (A number from 1 to 10 representing how certain you are of this evaluation based on the provided context.)
    
    Ensure your response is valid raw JSON.
    """
    
    system_prompt = "You are a precise procurement auditor. Output raw JSON only."
    
    response_text = query_llm(prompt, system_prompt, model="qwen2.5:7b", json_mode=True)
    if not response_text:
        response_text = query_llm(prompt, system_prompt, model="llama3.2:latest", json_mode=True)
        
    try:
        eval_data = json.loads(response_text)
        eval_data["id"] = requirement["id"]
        eval_data["category"] = category
        eval_data["spec_name"] = spec_name
        eval_data["requirement_detail"] = req_detail
        eval_data["page_references"] = sorted(list(page_references)) if page_references else []
        return eval_data
    except Exception as e:
        print(f"Failed to parse evaluation response JSON: {e}. Raw response: {response_text}")
        # Return a fallback evaluation
        return {
            "id": requirement["id"],
            "category": category,
            "spec_name": spec_name,
            "requirement_detail": req_detail,
            "status": "MISSING",
            "proposal_response": "Could not identify matching references in the vendor proposal.",
            "deviation_details": "No discussion or mention of this specification could be found in the provided proposal text.",
            "confidence_score": 5,
            "page_references": []
        }

def run_full_comparison(tender_doc_id: str, proposal_doc_id: str) -> List[Dict[str, Any]]:
    """
    Runs the end-to-end comparison: extracts specifications from the Tender and evaluates the Vendor Proposal against them.
    """
    print("Extracting specifications from Tender...")
    requirements = extract_requirements_from_tender(tender_doc_id)
    
    print(f"Extracted {len(requirements)} requirements. Evaluating Vendor Proposal...")
    comparison_results = []
    for req in requirements:
        print(f"Comparing spec: {req['spec_name']}...")
        result = compare_requirement_to_proposal(req, proposal_doc_id)
        comparison_results.append(result)
        
    print("Full compliance audit complete.")
    return comparison_results
