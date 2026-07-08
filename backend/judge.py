import os
import sqlite3
import json
import threading
import requests
from datetime import datetime
from typing import Dict, Any, List

DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "data", "audit_logs.db")
OLLAMA_URL = "http://localhost:11434/api/generate"

def get_db_connection():
    os.makedirs(os.path.dirname(DB_FILE), exist_ok=True)
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Chat History table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS chat_history (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id TEXT NOT NULL,
        user_query TEXT NOT NULL,
        assistant_response TEXT NOT NULL,
        retrieved_context TEXT NOT NULL,
        feedback_value INTEGER DEFAULT 0, -- 1 = upvote, -1 = downvote, 0 = neutral
        timestamp TEXT NOT NULL
    )
    """)
    
    # Judge Evaluations table
    cursor.execute("""
    CREATE TABLE IF NOT EXISTS judge_evaluations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        chat_id INTEGER UNIQUE,
        faithfulness_score INTEGER,
        faithfulness_reason TEXT,
        retrieval_score INTEGER,
        retrieval_reason TEXT,
        relevance_score INTEGER,
        relevance_reason TEXT,
        failure_category TEXT,
        timestamp TEXT,
        FOREIGN KEY (chat_id) REFERENCES chat_history(id)
    )
    """)
    conn.commit()
    conn.close()

# Initialize DB on import
init_db()

def log_chat(session_id: str, query: str, response: str, context: str) -> int:
    """
    Logs a chat message and returns its ID.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    timestamp = datetime.now().isoformat()
    cursor.execute(
        "INSERT INTO chat_history (session_id, user_query, assistant_response, retrieved_context, timestamp) VALUES (?, ?, ?, ?, ?)",
        (session_id, query, response, context, timestamp)
    )
    chat_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return chat_id

def log_feedback(chat_id: int, feedback_value: int):
    """
    Saves user feedback (+1 or -1) and triggers evaluation on downvote.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE chat_history SET feedback_value = ? WHERE id = ?",
        (feedback_value, chat_id)
    )
    conn.commit()
    conn.close()
    
    if feedback_value == -1:
        # Trigger judge evaluation in a background thread to keep API responsive
        threading.Thread(target=run_judge_evaluation, args=(chat_id,)).start()

def run_judge_evaluation(chat_id: int):
    """
    Runs the LLM-as-a-Judge logic to audit the failed response.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    row = cursor.execute(
        "SELECT user_query, assistant_response, retrieved_context FROM chat_history WHERE id = ?",
        (chat_id,)
    ).fetchone()
    
    if not row:
        conn.close()
        return
        
    query = row["user_query"]
    response = row["assistant_response"]
    context = row["retrieved_context"]
    conn.close()
    
    prompt = f"""
    You are an objective AI Judge evaluating a Retrieval-Augmented Generation (RAG) system's output.
    Analyze the following query, context retrieved from the database, and the system response.
    
    [USER QUERY]
    {query}
    
    [RETRIEVED CONTEXT]
    {context if context else "No context was retrieved."}
    
    [SYSTEM RESPONSE]
    {response}
    
    Grade the system response on 3 criteria (score 1 for Good/Pass, 0 for Bad/Fail):
    1. Faithfulness (hallucination): Is the response fully grounded in the retrieved context? If it mentions facts not in the context, score 0.
    2. Retrieval Quality: Was the context retrieved relevant to the query and did it contain the info needed? If context was irrelevant or empty, score 0.
    3. Answer Relevance: Did the response answer the user's specific query directly and relevantly? If it was off-topic, evasive or empty, score 0.
    
    Based on these scores, identify the primary failure category:
    - "Hallucination": Grounding issue (faithfulness = 0).
    - "Retrieval Failure": Context irrelevant/insufficient (retrieval_quality = 0).
    - "Answer Irrelevance": Answer was off-topic or poor (answer_relevance = 0).
    - "None": No failures detected.
    
    Format the response strictly as a JSON object with this exact structure:
    {{
      "faithfulness": {{
        "score": 0 or 1,
        "reason": "Reason for faithfulness score"
      }},
      "retrieval_quality": {{
        "score": 0 or 1,
        "reason": "Reason for retrieval quality score"
      }},
      "answer_relevance": {{
        "score": 0 or 1,
        "reason": "Reason for answer relevance score"
      }},
      "failure_category": "Hallucination" | "Retrieval Failure" | "Answer Irrelevance" | "None"
    }}
    """
    
    payload = {
        "model": "qwen2.5:7b",
        "prompt": prompt,
        "stream": False,
        "format": "json"
    }
    
    try:
        res = requests.post(OLLAMA_URL, json=payload, timeout=60)
        res.raise_for_status()
        judge_res = json.loads(res.json()["response"])
    except Exception as e:
        print(f"Judge LLM execution error: {e}")
        # Try fallback model
        try:
            payload["model"] = "llama3.2:latest"
            res = requests.post(OLLAMA_URL, json=payload, timeout=60)
            res.raise_for_status()
            judge_res = json.loads(res.json()["response"])
        except Exception as fallback_e:
            print(f"Fallback judge failed: {fallback_e}")
            judge_res = {
                "faithfulness": {"score": 0, "reason": "Failed to run evaluation"},
                "retrieval_quality": {"score": 0, "reason": "Failed to run evaluation"},
                "answer_relevance": {"score": 0, "reason": "Failed to run evaluation"},
                "failure_category": "Retrieval Failure"
            }
            
    # Save judge result in DB
    timestamp = datetime.now().isoformat()
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
    INSERT OR REPLACE INTO judge_evaluations (
        chat_id, faithfulness_score, faithfulness_reason, 
        retrieval_score, retrieval_reason, relevance_score, 
        relevance_reason, failure_category, timestamp
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        chat_id,
        judge_res["faithfulness"]["score"],
        judge_res["faithfulness"]["reason"],
        judge_res["retrieval_quality"]["score"],
        judge_res["retrieval_quality"]["reason"],
        judge_res["answer_relevance"]["score"],
        judge_res["answer_relevance"]["reason"],
        judge_res["failure_category"],
        timestamp
    ))
    conn.commit()
    conn.close()
    print(f"Logged judge evaluation for chat ID {chat_id}: Category = {judge_res['failure_category']}")

def get_analytics_summary() -> Dict[str, Any]:
    """
    Queries SQLite database and compiles statistics for the dashboard.
    """
    conn = get_db_connection()
    cursor = conn.cursor()
    
    total_chats = cursor.execute("SELECT COUNT(*) FROM chat_history").fetchone()[0]
    total_upvotes = cursor.execute("SELECT COUNT(*) FROM chat_history WHERE feedback_value = 1").fetchone()[0]
    total_downvotes = cursor.execute("SELECT COUNT(*) FROM chat_history WHERE feedback_value = -1").fetchone()[0]
    
    # Failure category counts
    failure_rows = cursor.execute("""
        SELECT failure_category, COUNT(*) as count 
        FROM judge_evaluations 
        GROUP BY failure_category
    """).fetchall()
    
    failures = {row["failure_category"]: row["count"] for row in failure_rows}
    # Ensure default fields are present
    for key in ["Hallucination", "Retrieval Failure", "Answer Irrelevance", "None"]:
        failures.setdefault(key, 0)
        
    # Detail list of evaluations for audit log
    audit_logs = []
    log_rows = cursor.execute("""
        SELECT h.id as chat_id, h.user_query, h.assistant_response, 
               e.faithfulness_score, e.faithfulness_reason, 
               e.retrieval_score, e.retrieval_reason,
               e.relevance_score, e.relevance_reason,
               e.failure_category, e.timestamp
        FROM judge_evaluations e
        JOIN chat_history h ON e.chat_id = h.id
        ORDER BY e.timestamp DESC
        LIMIT 10
    """).fetchall()
    
    for row in log_rows:
        audit_logs.append({
            "chat_id": row["chat_id"],
            "query": row["user_query"],
            "response": row["assistant_response"],
            "faithfulness": {"score": row["faithfulness_score"], "reason": row["faithfulness_reason"]},
            "retrieval": {"score": row["retrieval_score"], "reason": row["retrieval_reason"]},
            "relevance": {"score": row["relevance_score"], "reason": row["relevance_reason"]},
            "failure_category": row["failure_category"],
            "timestamp": row["timestamp"]
        })
        
    # Calculate daily feedback logs for chart
    daily_history = []
    history_rows = cursor.execute("""
        SELECT DATE(timestamp) as date, 
               SUM(CASE WHEN feedback_value = 1 THEN 1 ELSE 0 END) as upvotes,
               SUM(CASE WHEN feedback_value = -1 THEN 1 ELSE 0 END) as downvotes
        FROM chat_history
        GROUP BY DATE(timestamp)
        ORDER BY date ASC
        LIMIT 7
    """).fetchall()
    
    for row in history_rows:
        daily_history.append({
            "date": row["date"],
            "upvotes": row["upvotes"],
            "downvotes": row["downvotes"]
        })
        
    conn.close()
    
    return {
        "total_chats": total_chats,
        "upvotes": total_upvotes,
        "downvotes": total_downvotes,
        "failures": failures,
        "audit_logs": audit_logs,
        "daily_history": daily_history
    }
