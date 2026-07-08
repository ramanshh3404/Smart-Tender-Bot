import React, { useState, useEffect, useRef } from "react";
import {
  Upload,
  ShieldAlert,
  MessageSquare,
  BarChart3,
  CheckCircle2,
  AlertTriangle,
  FileText,
  ThumbsUp,
  ThumbsDown,
  Loader2,
  Search,
  ArrowRight,
  ChevronRight,
  ChevronDown,
  Info,
  RefreshCw,
  Send,
  Sparkles,
  HelpCircle,
  FileSearch,
  CheckSquare
} from "lucide-react";
import "./App.css";

const API_BASE = "http://localhost:8000/api";

function App() {
  const [activeTab, setActiveTab] = useState("upload");

  // Document Upload States
  const [tenderFile, setTenderFile] = useState(null);
  const [proposalFile, setProposalFile] = useState(null);
  const [uploadingTender, setUploadingTender] = useState(false);
  const [uploadingProposal, setUploadingProposal] = useState(false);
  const [tenderInfo, setTenderInfo] = useState(null); // { doc_id, filename, num_parent_chunks }
  const [proposalInfo, setProposalInfo] = useState(null); // { doc_id, filename, num_parent_chunks }

  // Document Comparison States
  const [comparing, setComparing] = useState(false);
  const [comparisonResults, setComparisonResults] = useState(null); // List of specifications
  const [expandedSpecId, setExpandedSpecId] = useState(null);
  const [specSearch, setSpecSearch] = useState("");
  const [specFilter, setSpecFilter] = useState("ALL");

  // Chat Interface States
  const [chatMessages, setChatMessages] = useState([]);
  const [chatQuery, setChatQuery] = useState("");
  const [chatting, setChatting] = useState(false);
  const [chatDocType, setChatDocType] = useState("proposal"); // "tender" or "proposal"
  const chatEndRef = useRef(null);

  // Analytics States
  const [analyticsData, setAnalyticsData] = useState(null);
  const [loadingAnalytics, setLoadingAnalytics] = useState(false);

  // Auto-scroll chat to bottom
  useEffect(() => {
    chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages]);

  // Load analytics when analytics tab is clicked
  useEffect(() => {
    if (activeTab === "analytics") {
      fetchAnalytics();
    }
  }, [activeTab]);

  const fetchAnalytics = async () => {
    setLoadingAnalytics(true);
    try {
      const response = await fetch(`${API_BASE}/analytics`);
      const data = await response.json();
      if (data.success) {
        setAnalyticsData(data.data);
      }
    } catch (error) {
      console.error("Error fetching analytics:", error);
    } finally {
      setLoadingAnalytics(false);
    }
  };

  const handleFileUpload = async (file, docType) => {
    if (!file) return;
    
    if (docType === "tender") {
      setUploadingTender(true);
    } else {
      setUploadingProposal(true);
    }

    const formData = new FormData();
    formData.append("file", file);
    formData.append("doc_type", docType);

    try {
      const response = await fetch(`${API_BASE}/upload`, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        throw new Error(await response.text());
      }

      const data = await response.json();
      if (data.success) {
        if (docType === "tender") {
          setTenderInfo({
            doc_id: data.doc_id,
            filename: data.filename,
            chunks: data.num_parent_chunks
          });
        } else {
          setProposalInfo({
            doc_id: data.doc_id,
            filename: data.filename,
            chunks: data.num_parent_chunks
          });
        }
      }
    } catch (error) {
      alert(`Upload failed: ${error.message}`);
    } finally {
      if (docType === "tender") {
        setUploadingTender(false);
      } else {
        setUploadingProposal(false);
      }
    }
  };

  const runComparison = async () => {
    if (!tenderInfo || !proposalInfo) return;
    setComparing(true);
    setActiveTab("compliance");

    try {
      const response = await fetch(`${API_BASE}/compare`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          tender_doc_id: tenderInfo.doc_id,
          proposal_doc_id: proposalInfo.doc_id
        }),
      });

      if (!response.ok) throw new Error("Comparison request failed");
      const data = await response.json();
      if (data.success) {
        setComparisonResults(data.results);
      }
    } catch (error) {
      alert(`Comparison failed: ${error.message}`);
      setActiveTab("upload");
    } finally {
      setComparing(false);
    }
  };

  const sendChatMessage = async (e) => {
    e.preventDefault();
    if (!chatQuery.trim()) return;

    const docIds = [];
    if (tenderInfo?.doc_id) docIds.push(tenderInfo.doc_id);
    if (proposalInfo?.doc_id) docIds.push(proposalInfo.doc_id);

    if (docIds.length === 0) {
      alert("Please upload the Tender and/or Proposal PDF first.");
      return;
    }

    const userMessage = {
      id: Date.now(),
      sender: "user",
      text: chatQuery
    };

    setChatMessages((prev) => [...prev, userMessage]);
    setChatQuery("");
    setChatting(true);

    try {
      const response = await fetch(`${API_BASE}/chat`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          doc_id: docIds,
          session_id: "default_session",
          query: userMessage.text
        })
      });

      if (!response.ok) throw new Error("Failed to get chatbot response");
      const data = await response.json();

      if (data.success) {
        setChatMessages((prev) => [
          ...prev,
          {
            id: Date.now() + 1,
            sender: "assistant",
            text: data.response,
            chat_id: data.chat_id,
            feedback: 0, // 0 = none, 1 = upvoted, -1 = downvoted
            references: data.references
          }
        ]);
      }
    } catch (error) {
      setChatMessages((prev) => [
        ...prev,
        {
          id: Date.now() + 1,
          sender: "assistant",
          text: `Error: ${error.message}. Please check if Ollama is running local models.`,
          error: true
        }
      ]);
    } finally {
      setChatting(false);
    }
  };

  const handleFeedback = async (chatId, val, messageIndex) => {
    try {
      const response = await fetch(`${API_BASE}/feedback`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          chat_id: chatId,
          value: val
        })
      });

      if (response.ok) {
        setChatMessages((prev) => {
          const updated = [...prev];
          updated[messageIndex].feedback = val;
          return updated;
        });
        
        if (val === -1) {
          alert("Your downvote was logged. The LLM-as-a-Judge agent is analyzing why this response failed in the background. Visit the Analytics tab to view results.");
        }
      }
    } catch (error) {
      console.error("Error submitting feedback:", error);
    }
  };

  // Helper to filter comparison items
  const filteredSpecs = comparisonResults
    ? comparisonResults.filter((spec) => {
        const matchesSearch =
          spec.spec_name.toLowerCase().includes(specSearch.toLowerCase()) ||
          spec.requirement_detail.toLowerCase().includes(specSearch.toLowerCase()) ||
          spec.proposal_response.toLowerCase().includes(specSearch.toLowerCase());
        const matchesFilter = specFilter === "ALL" || spec.status === specFilter;
        return matchesSearch && matchesFilter;
      })
    : [];

  const getStatusCounts = () => {
    if (!comparisonResults) return { compliant: 0, deviation: 0, partial: 0, missing: 0 };
    return {
      compliant: comparisonResults.filter((r) => r.status === "COMPLIANT").length,
      deviation: comparisonResults.filter((r) => r.status === "DEVIATION").length,
      partial: comparisonResults.filter((r) => r.status === "PARTIAL").length,
      missing: comparisonResults.filter((r) => r.status === "MISSING").length,
    };
  };

  const counts = getStatusCounts();

  return (
    <div className="app-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div className="brand">
          <h2>TenderSmart Bot</h2>
          <span>ONGC Procurement AI</span>
        </div>

        <ul className="nav-menu">
          <li
            className={`nav-item ${activeTab === "upload" ? "active" : ""}`}
            onClick={() => setActiveTab("upload")}
          >
            <Upload size={18} />
            Upload Desk
          </li>
          <li
            className={`nav-item ${activeTab === "compliance" ? "active" : ""} ${
              !comparisonResults && !comparing ? "disabled-nav" : ""
            }`}
            onClick={() => comparisonResults && setActiveTab("compliance")}
            style={{
              opacity: !comparisonResults && !comparing ? 0.5 : 1,
              cursor: !comparisonResults && !comparing ? "not-allowed" : "pointer",
            }}
          >
            <ShieldAlert size={18} />
            Compliance Table
          </li>
          <li
            className={`nav-item ${activeTab === "chat" ? "active" : ""} ${
              !tenderInfo && !proposalInfo ? "disabled-nav" : ""
            }`}
            onClick={() => (tenderInfo || proposalInfo) && setActiveTab("chat")}
            style={{
              opacity: !tenderInfo && !proposalInfo ? 0.5 : 1,
              cursor: !tenderInfo && !proposalInfo ? "not-allowed" : "pointer",
            }}
          >
            <MessageSquare size={18} />
            Query Bot (RAG)
          </li>
          <li
            className={`nav-item ${activeTab === "analytics" ? "active" : ""}`}
            onClick={() => setActiveTab("analytics")}
          >
            <BarChart3 size={18} />
            Auditor Analytics
          </li>
        </ul>

        {/* Footer Stats / Status */}
        <div style={{ marginTop: "auto", borderTop: "1px solid var(--border-subtle)", paddingTop: "1.5rem" }}>
          <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem", fontSize: "0.8rem", color: "var(--text-secondary)" }}>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>Ollama Status:</span>
              <span style={{ color: "var(--color-compliant)", fontWeight: 600 }}>Active</span>
            </div>
            <div style={{ display: "flex", justifyContent: "space-between" }}>
              <span>ChromaDB:</span>
              <span style={{ color: "var(--color-compliant)", fontWeight: 600 }}>Connected</span>
            </div>
          </div>
        </div>
      </aside>

      {/* Main Content Workspace */}
      <main className="main-content">
        
        {/* TAB 1: UPLOAD DESK */}
        {activeTab === "upload" && (
          <div className="tab-panel">
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <h1 style={{ fontSize: "2rem", fontFamily: "var(--font-display)" }}>Procurement Documents Desk</h1>
              <p style={{ color: "var(--text-secondary)" }}>
                Upload the ONGC Tender requirements PDF and the Vendor's technical proposal PDF to compare specifications.
              </p>
            </div>

            <div className="upload-grid">
              
              {/* TENDER UPLOAD */}
              <div className="upload-card glow-hover">
                <div className="file-icon-wrapper">
                  <FileSearch size={32} />
                </div>
                <div>
                  <h3>ONGC Tender Document</h3>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                    The floating tender containing specifications and standards.
                  </p>
                </div>
                
                {tenderInfo ? (
                  <div className="file-info">
                    <CheckSquare size={16} style={{ color: "var(--color-compliant)" }} />
                    <span style={{ fontWeight: 500 }}>{tenderInfo.filename}</span>
                    <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>({tenderInfo.chunks} sections)</span>
                  </div>
                ) : (
                  <label className="upload-label">
                    Select Tender PDF
                    <input
                      type="file"
                      accept=".pdf"
                      className="file-input"
                      onChange={(e) => {
                        const file = e.target.files[0];
                        setTenderFile(file);
                        handleFileUpload(file, "tender");
                      }}
                    />
                  </label>
                )}

                {uploadingTender && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.9rem" }}>
                    <Loader2 size={16} className="spin" style={{ animation: "spin 1s linear infinite" }} />
                    <span>Parsing and building Parent-Child chunks...</span>
                  </div>
                )}
              </div>

              {/* PROPOSAL UPLOAD */}
              <div className="upload-card glow-hover">
                <div className="file-icon-wrapper">
                  <FileText size={32} style={{ color: "var(--accent-purple)" }} />
                </div>
                <div>
                  <h3>Vendor Proposal PDF</h3>
                  <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "0.25rem" }}>
                    The technical specifications bid submitted by the vendor.
                  </p>
                </div>

                {proposalInfo ? (
                  <div className="file-info">
                    <CheckSquare size={16} style={{ color: "var(--color-compliant)" }} />
                    <span style={{ fontWeight: 500 }}>{proposalInfo.filename}</span>
                    <span style={{ color: "var(--text-muted)", fontSize: "0.75rem" }}>({proposalInfo.chunks} sections)</span>
                  </div>
                ) : (
                  <label className="upload-label" style={{ background: "rgba(168, 85, 247, 0.15)", borderColor: "rgba(168, 85, 247, 0.3)" }}>
                    Select Proposal PDF
                    <input
                      type="file"
                      accept=".pdf"
                      className="file-input"
                      onChange={(e) => {
                        const file = e.target.files[0];
                        setProposalFile(file);
                        handleFileUpload(file, "proposal");
                      }}
                    />
                  </label>
                )}

                {uploadingProposal && (
                  <div style={{ display: "flex", alignItems: "center", gap: "0.5rem", fontSize: "0.9rem" }}>
                    <Loader2 size={16} className="spin" style={{ animation: "spin 1s linear infinite" }} />
                    <span>Parsing and building Parent-Child chunks...</span>
                  </div>
                )}
              </div>
            </div>

            {tenderInfo && proposalInfo && (
              <div style={{ display: "flex", justifyContent: "center", marginTop: "2rem" }}>
                <button
                  className="btn-primary"
                  onClick={runComparison}
                  disabled={comparing}
                  style={{ width: "280px" }}
                >
                  {comparing ? (
                    <>
                      <Loader2 size={18} className="spin" style={{ animation: "spin 1s linear infinite" }} />
                      Comparing Specs (Hybrid Search)...
                    </>
                  ) : (
                    <>
                      Verify Compliance Matrix
                      <ArrowRight size={18} />
                    </>
                  )}
                </button>
              </div>
            )}
          </div>
        )}

        {/* TAB 2: COMPLIANCE MATRIX */}
        {activeTab === "compliance" && (
          <div className="tab-panel">
            {comparing ? (
              <div className="empty-state">
                <Loader2 size={48} className="spin" style={{ color: "var(--accent-indigo)", animation: "spin 2s linear infinite" }} />
                <h2>Auditing Specifications</h2>
                <p>
                  Comparing Tender requirements against Vendor Proposal using local LLM... This may take up to a minute.
                </p>
              </div>
            ) : (
              <>
                <div style={{ display: "flex", justifyContent: "between", alignItems: "center", flexWrap: "wrap", gap: "1rem" }}>
                  <div>
                    <h1 style={{ fontSize: "2rem", fontFamily: "var(--font-display)" }}>Compliance Matrix</h1>
                    <p style={{ color: "var(--text-secondary)" }}>
                      Detailed comparison showing deviations, compliance status, and page citations in Vendor Proposal.
                    </p>
                  </div>
                </div>

                {/* Summary Badges Grid */}
                <div className="compliance-summary">
                  <div className="summary-card glass-panel" style={{ borderLeft: "4px solid var(--color-compliant)" }}>
                    <h4>Compliant Items</h4>
                    <span className="number" style={{ color: "var(--color-compliant)" }}>{counts.compliant}</span>
                  </div>
                  <div className="summary-card glass-panel" style={{ borderLeft: "4px solid var(--color-deviation)" }}>
                    <h4>Deviations</h4>
                    <span className="number" style={{ color: "var(--color-deviation)" }}>{counts.deviation}</span>
                  </div>
                  <div className="summary-card glass-panel" style={{ borderLeft: "4px solid var(--color-partial)" }}>
                    <h4>Partials</h4>
                    <span className="number" style={{ color: "var(--color-partial)" }}>{counts.partial}</span>
                  </div>
                  <div className="summary-card glass-panel" style={{ borderLeft: "4px solid var(--color-missing)" }}>
                    <h4>Missing Docs / Flags</h4>
                    <span className="number" style={{ color: "var(--color-missing)" }}>{counts.missing}</span>
                  </div>
                </div>

                {/* Filters */}
                <div className="filter-bar">
                  <div className="search-input-wrapper">
                    <Search size={16} className="search-icon" />
                    <input
                      type="text"
                      placeholder="Search specifications, requirements, or proposal response..."
                      value={specSearch}
                      onChange={(e) => setSpecSearch(e.target.value)}
                    />
                  </div>
                  
                  <select
                    className="filter-select"
                    value={specFilter}
                    onChange={(e) => setSpecFilter(e.target.value)}
                  >
                    <option value="ALL">All Statuses</option>
                    <option value="COMPLIANT">Compliant</option>
                    <option value="DEVIATION">Deviations</option>
                    <option value="PARTIAL">Partials</option>
                    <option value="MISSING">Missing / Flags</option>
                  </select>
                </div>

                {/* Compliance Table */}
                <div className="table-container glass-panel">
                  <table className="compliance-table">
                    <thead>
                      <tr>
                        <th>Spec Details</th>
                        <th>Category</th>
                        <th>Status</th>
                        <th>Confidence</th>
                        <th>Proposal Page</th>
                        <th>Details</th>
                      </tr>
                    </thead>
                    <tbody>
                      {filteredSpecs.map((spec) => {
                        const isExpanded = expandedSpecId === spec.id;
                        return (
                          <React.Fragment key={spec.id}>
                            <tr 
                              style={{ cursor: "pointer" }}
                              onClick={() => setExpandedSpecId(isExpanded ? null : spec.id)}
                            >
                              <td>
                                <div style={{ fontWeight: 600 }}>{spec.spec_name}</div>
                                <div style={{ fontSize: "0.85rem", color: "var(--text-secondary)", textOverflow: "ellipsis", overflow: "hidden", whiteSpace: "nowrap", maxWidth: "450px" }}>
                                  {spec.requirement_detail}
                                </div>
                              </td>
                              <td>{spec.category}</td>
                              <td>
                                <span className={`badge ${spec.status.toLowerCase()}`}>
                                  {spec.status}
                                </span>
                              </td>
                              <td style={{ fontWeight: 600 }}>{spec.confidence_score}/10</td>
                              <td>
                                {spec.page_references.length > 0 
                                  ? `Page ${spec.page_references.join(", ")}` 
                                  : "N/A"}
                              </td>
                              <td>
                                {isExpanded ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                              </td>
                            </tr>
                            
                            {isExpanded && (
                              <tr>
                                <td colSpan="6" style={{ background: "rgba(255, 255, 255, 0.015)", padding: "1.5rem" }}>
                                  <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
                                    <div>
                                      <h5 style={{ color: "var(--text-secondary)", marginBottom: "0.25rem" }}>Tender Requirement Details:</h5>
                                      <p style={{ fontSize: "0.95rem" }}>{spec.requirement_detail}</p>
                                    </div>
                                    <div style={{ borderLeft: "3px solid var(--accent-indigo)", paddingLeft: "1rem" }}>
                                      <h5 style={{ color: "var(--accent-indigo)", marginBottom: "0.25rem" }}>Vendor Proposal Response:</h5>
                                      <p style={{ fontSize: "0.95rem" }}>{spec.proposal_response}</p>
                                    </div>
                                    {(spec.status === "DEVIATION" || spec.status === "PARTIAL" || spec.status === "MISSING") && (
                                      <div style={{ borderLeft: "3px solid var(--color-missing)", paddingLeft: "1rem", background: "rgba(239, 68, 68, 0.02)", padding: "0.75rem" }}>
                                        <h5 style={{ color: "var(--color-missing)", marginBottom: "0.25rem" }}>Deviation & Compliance Flags:</h5>
                                        <p style={{ fontSize: "0.95rem" }}>{spec.deviation_details}</p>
                                      </div>
                                    )}
                                  </div>
                                </td>
                              </tr>
                            )}
                          </React.Fragment>
                        );
                      })}
                      
                      {filteredSpecs.length === 0 && (
                        <tr>
                          <td colSpan="6" style={{ textAlign: "center", color: "var(--text-muted)", padding: "3rem" }}>
                            No specifications found matching the search/filter criteria.
                          </td>
                        </tr>
                      )}
                    </tbody>
                  </table>
                </div>
              </>
            )}
          </div>
        )}

        {/* TAB 3: QUERY BOT */}
        {activeTab === "chat" && (
          <div className="tab-panel">
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <h1 style={{ fontSize: "2rem", fontFamily: "var(--font-display)" }}>Tender Query Bot</h1>
              <p style={{ color: "var(--text-secondary)" }}>
                Chat directly with the Tender Requirements or Vendor Proposal using Hybrid Search (BM25 + Vector) RAG.
              </p>
            </div>

            <div className="chat-container glass-panel">
              <div className="chat-header">
                <div style={{ display: "flex", gap: "0.5rem", alignItems: "center" }}>
                  <Sparkles size={16} style={{ color: "var(--accent-blue)" }} />
                  <span style={{ fontWeight: 600 }}>Active Search Mode:</span>
                  <span className="badge compliant" style={{ fontSize: '0.75rem', textTransform: 'none', letterSpacing: 'normal' }}>
                    Tender + Vendor Proposal (Cross-Document Synthesis)
                  </span>
                </div>
              </div>

              <div className="chat-messages">
                {chatMessages.length === 0 ? (
                  <div className="empty-state" style={{ height: "100%", justifyContent: "center" }}>
                    <MessageSquare size={36} />
                    <h3>No queries started</h3>
                    <p>Ask anything about the specifications, materials, standards or delivery times in the document.</p>
                    <div style={{ display: "flex", gap: "0.5rem", flexWrap: "wrap", justifyContent: "center", marginTop: "1rem" }}>
                      <button 
                        className="upload-label" 
                        onClick={() => setChatQuery("Is there any deviation on the pipeline steel grade?")}
                        style={{ padding: "0.5rem 1rem", fontSize: "0.8rem" }}
                      >
                        "Is there any deviation on the pipeline steel grade?"
                      </button>
                      <button 
                        className="upload-label" 
                        onClick={() => setChatQuery("Does the vendor provide API Spec Q1 and ISO 9001 certificates?")}
                        style={{ padding: "0.5rem 1rem", fontSize: "0.8rem" }}
                      >
                        "Does the vendor provide API Spec Q1 certificates?"
                      </button>
                    </div>
                  </div>
                ) : (
                  chatMessages.map((msg, index) => (
                    <div key={msg.id} className={`message ${msg.sender}`}>
                      <div className="avatar">
                        {msg.sender === "user" ? "U" : "AI"}
                      </div>
                      <div className="message-bubble">
                        <p style={{ whiteSpace: "pre-wrap" }}>{msg.text}</p>
                        
                        {msg.sender === "assistant" && msg.references && msg.references.length > 0 && (
                          <div className="references-section">
                            <span style={{ fontWeight: 600, display: "block", marginBottom: "0.25rem" }}>
                              References (Parent Chunks):
                            </span>
                            {msg.references.map((ref, rIdx) => (
                              <span key={rIdx} className="reference-tag" title={ref.text}>
                                {ref.filename} (Page {ref.pages.join(", ")})
                              </span>
                            ))}
                          </div>
                        )}

                        {msg.sender === "assistant" && !msg.error && (
                          <div className="message-actions">
                            <button
                              className={`action-btn upvote ${msg.feedback === 1 ? "active" : ""}`}
                              onClick={() => handleFeedback(msg.chat_id, 1, index)}
                              title="Helpful Response"
                            >
                              <ThumbsUp size={14} />
                            </button>
                            <button
                              className={`action-btn downvote ${msg.feedback === -1 ? "active" : ""}`}
                              onClick={() => handleFeedback(msg.chat_id, -1, index)}
                              title="Unhelpful / Inaccurate Response"
                            >
                              <ThumbsDown size={14} />
                            </button>
                          </div>
                        )}
                      </div>
                    </div>
                  ))
                )}
                {chatting && (
                  <div className="message assistant">
                    <div className="avatar">
                      <Loader2 size={16} className="spin" style={{ animation: "spin 1s linear infinite" }} />
                    </div>
                    <div className="message-bubble" style={{ color: "var(--text-secondary)" }}>
                      Scanning document (BM25 + ChromaDB Hybrid)...
                    </div>
                  </div>
                )}
                <div ref={chatEndRef} />
              </div>

              <form onSubmit={sendChatMessage} className="chat-input-area">
                <input
                  type="text"
                  placeholder="Ask a question about the Tender or Proposal..."
                  value={chatQuery}
                  onChange={(e) => setChatQuery(e.target.value)}
                  disabled={chatting}
                />
                <button type="submit" className="btn-primary" style={{ padding: "0.85rem 1.25rem" }} disabled={chatting}>
                  <Send size={16} />
                </button>
              </form>
            </div>
          </div>
        )}

        {/* TAB 4: AUDITOR ANALYTICS */}
        {activeTab === "analytics" && (
          <div className="tab-panel">
            <div style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
              <h1 style={{ fontSize: "2rem", fontFamily: "var(--font-display)" }}>Auditor Analytics</h1>
              <p style={{ color: "var(--text-secondary)" }}>
                Background analytics generated by the <strong>LLM-as-a-Judge</strong> daemon, categorizing chat limitations and failures.
              </p>
            </div>

            {loadingAnalytics && !analyticsData ? (
              <div className="empty-state">
                <Loader2 size={36} className="spin" style={{ animation: "spin 2s linear infinite" }} />
                <span>Loading Judge diagnostics logs...</span>
              </div>
            ) : analyticsData ? (
              <div className="tab-panel">
                {/* Metric Summary Grid */}
                <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fit, minmax(220px, 1fr))", gap: "1.5rem" }}>
                  <div className="analytics-card glass-panel" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Total RAG Queries</span>
                    <span style={{ fontSize: "2rem", fontWeight: 800 }}>{analyticsData.total_chats}</span>
                  </div>
                  <div className="analytics-card glass-panel" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Upvotes (Helpful)</span>
                    <span style={{ fontSize: "2rem", fontWeight: 800, color: "var(--color-compliant)" }}>{analyticsData.upvotes}</span>
                  </div>
                  <div className="analytics-card glass-panel" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>Downvotes (Audited)</span>
                    <span style={{ fontSize: "2rem", fontWeight: 800, color: "var(--color-missing)" }}>{analyticsData.downvotes}</span>
                  </div>
                  <div className="analytics-card glass-panel" style={{ display: "flex", flexDirection: "column", gap: "0.5rem" }}>
                    <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>User Approval Rating</span>
                    <span style={{ fontSize: "2rem", fontWeight: 800, color: "var(--accent-blue)" }}>
                      {analyticsData.total_chats > 0 
                        ? `${Math.round((analyticsData.upvotes / (analyticsData.upvotes + analyticsData.downvotes || 1)) * 100)}%` 
                        : "100%"}
                    </span>
                  </div>
                </div>

                <div className="analytics-grid">
                  
                  {/* Failure Distribution */}
                  <div className="analytics-card glass-panel" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                    <h3>LLM-as-a-Judge Failures</h3>
                    <p style={{ fontSize: "0.85rem", color: "var(--text-secondary)", marginTop: "-1rem" }}>
                      Breakdown of downvoted queries evaluated by the auditor model (Llama3.2/Qwen2.5).
                    </p>

                    <div style={{ display: "flex", flexDirection: "column", gap: "1.25rem" }}>
                      {[
                        { label: "Hallucination (Faithfulness Error)", value: analyticsData.failures["Hallucination"] || 0, color: "var(--color-missing)" },
                        { label: "Retrieval Failure (Irrelevant Context)", value: analyticsData.failures["Retrieval Failure"] || 0, color: "var(--color-deviation)" },
                        { label: "Answer Irrelevance (Off-topic Output)", value: analyticsData.failures["Answer Irrelevance"] || 0, color: "var(--accent-indigo)" },
                        { label: "None (False Downvote/Acceptable)", value: analyticsData.failures["None"] || 0, color: "var(--color-compliant)" }
                      ].map((item, idx) => {
                        const totalFailures = Object.values(analyticsData.failures).reduce((a, b) => a + b, 0) || 1;
                        const percentage = Math.round((item.value / totalFailures) * 100);
                        return (
                          <div key={idx} style={{ display: "flex", flexDirection: "column", gap: "0.35rem" }}>
                            <div style={{ display: "flex", justifyContent: "space-between", fontSize: "0.85rem" }}>
                              <span>{item.label}</span>
                              <span style={{ fontWeight: 600 }}>{item.value} ({percentage}%)</span>
                            </div>
                            <div style={{ width: "100%", height: "8px", background: "var(--bg-primary)", borderRadius: "4px", overflow: "hidden" }}>
                              <div style={{ width: `${percentage}%`, height: "100%", background: item.color, borderRadius: "4px" }} />
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>

                  {/* Audit Logs Feed */}
                  <div className="analytics-card glass-panel" style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>
                    <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
                      <h3>Judge Audit Feed</h3>
                      <button onClick={fetchAnalytics} className="action-btn" title="Refresh Logs">
                        <RefreshCw size={14} />
                      </button>
                    </div>

                    <div className="audit-feed">
                      {analyticsData.audit_logs.length === 0 ? (
                        <div style={{ textAlign: "center", color: "var(--text-muted)", padding: "3rem" }}>
                          No audited failures logged yet. (Downvote chats to trigger the judge agent).
                        </div>
                      ) : (
                        analyticsData.audit_logs.map((log) => (
                          <div key={log.chat_id} className="audit-item">
                            <div className="audit-header">
                              <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
                                Chat ID: #{log.chat_id}
                              </span>
                              <span className={`badge ${log.failure_category === "None" ? "compliant" : "missing"}`}>
                                {log.failure_category}
                              </span>
                            </div>
                            
                            <div style={{ fontSize: "0.85rem" }}>
                              <strong style={{ color: "var(--accent-blue)" }}>User:</strong> {log.query}
                            </div>
                            
                            <div className="audit-reason">
                              <strong>Judge Analysis:</strong>
                              <div style={{ fontSize: "0.8rem", marginTop: "0.25rem", color: "var(--text-primary)" }}>
                                {log.faithfulness.score === 0 && `• Hallucination: ${log.faithfulness.reason}\n`}
                                {log.retrieval.score === 0 && `• Retrieval: ${log.retrieval.reason}\n`}
                                {log.relevance.score === 0 && `• Relevance: ${log.relevance.reason}\n`}
                                {log.failure_category === "None" && `• Audit passed: Answer is correct according to context.`}
                              </div>
                            </div>
                          </div>
                        ))
                      )}
                    </div>
                  </div>

                </div>
              </div>
            ) : (
              <div className="empty-state">
                <HelpCircle size={36} />
                <h3>No analytics summary compiled</h3>
                <p>Chat logs and judge classifications will appear here once users submit feedback.</p>
              </div>
            )}
          </div>
        )}

      </main>
    </div>
  );
}

export default App;
