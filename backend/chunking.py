import re
import uuid
from pypdf import PdfReader
from typing import List, Dict, Tuple

def extract_text_with_pages(pdf_path: str) -> List[Dict]:
    """
    Extracts text from a PDF, returning a list of dicts with text and page numbers.
    """
    reader = PdfReader(pdf_path)
    pages_data = []
    
    for page_num, page in enumerate(reader.pages):
        text = page.extract_text()
        if text:
            # Clean basic characters
            text = text.replace('\u0000', '')
            pages_data.append({
                "page": page_num + 1,
                "text": text
            })
    return pages_data

def clean_paragraph(text: str) -> str:
    """
    Cleans excessive spaces and standardizes whitespace.
    """
    # Replace multiple spaces with a single space
    text = re.sub(r'[ \t]+', ' ', text)
    # Standardize newlines
    text = re.sub(r'\n+', '\n', text)
    return text.strip()

def create_parent_child_chunks(
    pdf_path: str, 
    doc_id: str, 
    parent_size: int = 1200, 
    child_size: int = 250, 
    child_overlap: int = 50
) -> Tuple[List[Dict], List[Dict]]:
    """
    Reads a PDF and returns:
    1. parent_chunks: list of larger text segments (paragraphs/sections)
    2. child_chunks: list of smaller overlapping chunks linked to parent_chunks.
    """
    pages_data = extract_text_with_pages(pdf_path)
    if not pages_data:
        return [], []
        
    filename = pdf_path.split('/')[-1].split('\\')[-1]
    
    # 1. Create Parent Chunks
    # First, let's assemble text while keeping track of page numbers
    parent_chunks = []
    current_parent_text = ""
    current_parent_pages = set()
    
    for page_data in pages_data:
        page_num = page_data["page"]
        text = page_data["text"]
        
        # Split text into paragraphs (double newlines, or lines that end with a period and are followed by capital letters)
        paragraphs = text.split("\n\n")
        
        for para in paragraphs:
            para_clean = clean_paragraph(para)
            if not para_clean:
                continue
                
            if len(current_parent_text) + len(para_clean) > parent_size and current_parent_text:
                # Save the current parent chunk
                parent_id = f"{doc_id}_p_{len(parent_chunks)}"
                parent_chunks.append({
                    "id": parent_id,
                    "text": current_parent_text.strip(),
                    "doc_id": doc_id,
                    "filename": filename,
                    "pages": sorted(list(current_parent_pages))
                })
                current_parent_text = para_clean
                current_parent_pages = {page_num}
            else:
                current_parent_text += "\n" + para_clean if current_parent_text else para_clean
                current_parent_pages.add(page_num)
                
    # Add final parent chunk if any text remains
    if current_parent_text:
        parent_id = f"{doc_id}_p_{len(parent_chunks)}"
        parent_chunks.append({
            "id": parent_id,
            "text": current_parent_text.strip(),
            "doc_id": doc_id,
            "filename": filename,
            "pages": sorted(list(current_parent_pages))
        })
        
    # Map parent_id -> parent_chunk
    parent_map = {p["id"]: p for p in parent_chunks}
    
    # 2. Create Child Chunks from Parent Chunks
    child_chunks = []
    
    for parent in parent_chunks:
        parent_id = parent["id"]
        parent_text = parent["text"]
        
        # Split parent text into sentences using simple regex
        sentences = re.split(r'(?<=[.!?])\s+', parent_text)
        
        current_child_text = ""
        for i, sentence in enumerate(sentences):
            sentence = sentence.strip()
            if not sentence:
                continue
                
            if len(current_child_text) + len(sentence) > child_size and current_child_text:
                child_id = f"{doc_id}_c_{len(child_chunks)}"
                child_chunks.append({
                    "id": child_id,
                    "parent_id": parent_id,
                    "text": current_child_text.strip(),
                    "doc_id": doc_id,
                    "filename": filename,
                    "pages": parent["pages"]
                })
                # Set up text for next child, including some overlap from previous child if possible
                overlap_words = current_child_text.split()[-5:] # Take last 5 words as overlap
                current_child_text = " ".join(overlap_words) + " " + sentence
            else:
                current_child_text += " " + sentence if current_child_text else sentence
                
        # Add final child chunk for this parent
        if current_child_text:
            child_id = f"{doc_id}_c_{len(child_chunks)}"
            child_chunks.append({
                "id": child_id,
                "parent_id": parent_id,
                "text": current_child_text.strip(),
                "doc_id": doc_id,
                "filename": filename,
                "pages": parent["pages"]
            })
            
    return parent_chunks, child_chunks
