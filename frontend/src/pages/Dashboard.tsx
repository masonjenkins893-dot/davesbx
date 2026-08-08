import React, { useState, useEffect, useRef, useCallback } from "react";
import { ApiContext } from "../App";
import { Copy, Eye, EyeOff, Plus, X, Terminal as TerminalIcon, Folder, FileText, ChevronRight, ChevronDown } from "lucide-react";

interface FileNode {
  name: string;
  path: string;
  type: string;
  size: number;
  children?: FileNode[];
}

interface TerminalSession {
  id: string;
  output: string;
  command: string;
}

export function Dashboard() {
  const api = React.useContext(ApiContext);
  const [publicUrl, setPublicUrl] = useState("");
  const [apiKey, setApiKey] = useState(api.apiKey);
  const [showKey, setShowKey] = useState(false);
  const [authEnabled, setAuthEnabled] = useState(true);
  const [fileTree, setFileTree] = useState<FileNode | null>(null);
  const [selectedFile, setSelectedFile] = useState<string | null>(null);
  const [fileContent, setFileContent] = useState<string>("");
  const [terminals, setTerminals] = useState<TerminalSession[]>([]);
  const [activeTerminal, setActiveTerminal] = useState<string | null>(null);
  const [cmdInput, setCmdInput] = useState("");
  const outputRef = useRef<HTMLDivElement>(null);

  const headers = () => ({
    "Content-Type": "application/json",
    "X-API-Key": apiKey,
  });

  const copyToClipboard = (text: string) => {
    navigator.clipboard.writeText(text);
  };

  // Fetch config on mount
  useEffect(() => {
    fetch(`${api.baseUrl}/config`, { headers: headers() })
      .then((r) => r.json())
      .then((cfg) => {
        setPublicUrl(cfg.public_url || `${api.baseUrl}`);
        setAuthEnabled(cfg.auth_enabled ?? true);
      })
      .catch(() => {
        setPublicUrl(api.baseUrl);
      });
    refreshFileTree();
  }, []);

  // Fetch file tree
  const refreshFileTree = useCallback(async () => {
    try {
      const res = await fetch(`${api.baseUrl}/files/tree`, { headers: headers() });
      if (res.ok) {
        const tree = await res.json();
        setFileTree(tree);
      }
    } catch {}
  }, [api.baseUrl, apiKey]);

  // Auto-refresh file tree every 5 seconds
  useEffect(() => {
    const interval = setInterval(refreshFileTree, 5000);
    return () => clearInterval(interval);
  }, [refreshFileTree]);

  // Terminal management
  const createTerminal = async () => {
    try {
      const res = await fetch(`${api.baseUrl}/terminal/new`, {
        method: "POST",
        headers: headers(),
      });
      const data = await res.json();
      const newTerm: TerminalSession = { id: data.id, output: "", command: "" };
      setTerminals([...terminals, newTerm]);
      setActiveTerminal(data.id);
    } catch {}
  };

  const runCommand = async () => {
    if (!activeTerminal || !cmdInput.trim()) return;
    const cmd = cmdInput;
    setCmdInput("");

    // Update local output
    setTerminals((prev) =>
      prev.map((t) =>
        t.id === activeTerminal ? { ...t, output: t.output + `\n$ ${cmd}\n` } : t
      )
    );

    try {
      const res = await fetch(`${api.baseUrl}/terminal/${activeTerminal}/run`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({ command: cmd }),
      });
      const data = await res.json();

      if (data.error && data.options) {
        // Concurrency conflict
        setTerminals((prev) =>
          prev.map((t) =>
            t.id === activeTerminal
              ? { ...t, output: t.output + `⚠️ ${data.error}\n` }
              : t
          )
        );
      }
    } catch {}

    // Poll for output
    setTimeout(() => pollTerminalOutput(activeTerminal), 500);
  };

  const pollTerminalOutput = async (termId: string) => {
    try {
      const res = await fetch(`${api.baseUrl}/terminal/${termId}/output`, {
        headers: headers(),
      });
      const data = await res.json();
      setTerminals((prev) =>
        prev.map((t) => (t.id === termId ? { ...t, output: data.output || t.output } : t))
      );
    } catch {}
  };

  // Poll active terminal output
  useEffect(() => {
    if (!activeTerminal) return;
    const interval = setInterval(() => pollTerminalOutput(activeTerminal), 1000);
    return () => clearInterval(interval);
  }, [activeTerminal]);

  // Auto-scroll terminal output
  useEffect(() => {
    if (outputRef.current) {
      outputRef.current.scrollTop = outputRef.current.scrollHeight;
    }
  }, [terminals]);

  // Select file and preview
  const selectFile = async (path: string) => {
    setSelectedFile(path);
    try {
      const res = await fetch(`${api.baseUrl}/file/${path}?as_text=true`, {
        headers: headers(),
      });
      if (res.ok) {
        const data = await res.json();
        setFileContent(data.content || "[Binary file]");
      }
    } catch {
      setFileContent("[Failed to load file]");
    }
  };

  const toggleAuth = async () => {
    try {
      await fetch(`${api.baseUrl}/config/toggle-auth`, {
        method: "POST",
        headers: headers(),
      });
      setAuthEnabled(!authEnabled);
    } catch {}
  };

  // Render file tree recursively
  const renderTree = (node: FileNode, depth: number = 0): React.ReactNode => {
    if (!node.name && node.type === "directory") {
      return (node.children || []).map((child) => renderTree(child, depth));
    }
    return (
      <div key={node.path}>
        <div
          className={`file-tree-item ${selectedFile === node.path ? "selected" : ""}`}
          style={{ paddingLeft: `${10 + depth * 16}px` }}
          onClick={() => node.type === "file" && selectFile(node.path)}
        >
          {node.type === "directory" ? <Folder size={14} /> : <FileText size={14} />}
          <span>{node.name}</span>
        </div>
        {node.type === "directory" && node.children && (
          <div className="file-tree-children">
            {node.children.map((child) => renderTree(child, depth + 1))}
          </div>
        )}
      </div>
    );
  };

  return (
    <>
      {/* Top bar */}
      <div className="top-bar glass">
        <div className="url-display">
          <span>{publicUrl}</span>
          <button className="copy-btn" onClick={() => copyToClipboard(publicUrl)}>
            <Copy size={14} />
          </button>
        </div>
        <div className="key-display">
          <span>{showKey ? apiKey : "••••••••••••••••"}</span>
          <button className="copy-btn" onClick={() => setShowKey(!showKey)}>
            {showKey ? <EyeOff size={14} /> : <Eye size={14} />}
          </button>
          <button className="copy-btn" onClick={() => copyToClipboard(apiKey)}>
            <Copy size={14} />
          </button>
        </div>
        <div className="status-toggle">
          <div className="status-indicator">
            <div className={`status-dot ${authEnabled ? "" : "offline"}`}></div>
            <span>{authEnabled ? "API Active" : "API Paused"}</span>
          </div>
          <div className={`toggle-switch ${authEnabled ? "active" : ""}`} onClick={toggleAuth}></div>
        </div>
      </div>

      {/* Main area: file explorer + terminal */}
      <div style={{ flex: 1, display: "flex", gap: "16px", overflow: "hidden" }}>
        {/* File explorer */}
        <div className="glass" style={{ width: "300px", display: "flex", flexDirection: "column", flexShrink: 0 }}>
          <div style={{ padding: "12px 16px", fontSize: "13px", fontWeight: 600, color: "var(--text-secondary)", borderBottom: "1px solid var(--glass-border)" }}>
            Workspace Files
          </div>
          <div className="file-explorer">
            {fileTree ? renderTree(fileTree) : (
              <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
                Workspace is empty
              </div>
            )}
          </div>
        </div>

        {/* File preview */}
        <div className="glass" style={{ flex: 1, display: "flex", flexDirection: "column", maxWidth: "400px" }}>
          <div style={{ padding: "12px 16px", fontSize: "13px", fontWeight: 600, color: "var(--text-secondary)", borderBottom: "1px solid var(--glass-border)" }}>
            {selectedFile || "Preview"}
          </div>
          <div className="preview-pane">
            {selectedFile ? (
              <div className="preview-content">{fileContent}</div>
            ) : (
              <div style={{ color: "var(--text-muted)", fontSize: "13px", padding: "20px" }}>
                Select a file to preview its contents
              </div>
            )}
          </div>
        </div>

        {/* Terminal area */}
        <div className="glass terminal-container" style={{ flex: 1 }}>
          <div className="terminal-tabs">
            {terminals.map((t) => (
              <div
                key={t.id}
                className={`terminal-tab ${activeTerminal === t.id ? "active" : ""}`}
                onClick={() => setActiveTerminal(t.id)}
              >
                <TerminalIcon size={12} />
                <span>{t.id}</span>
                <span className="terminal-tab-close" onClick={(e) => {
                  e.stopPropagation();
                  setTerminals(terminals.filter((x) => x.id !== t.id));
                  if (activeTerminal === t.id) setActiveTerminal(terminals[0]?.id || null);
                }}>
                  <X size={12} />
                </span>
              </div>
            ))}
            <button className="new-tab-btn" onClick={createTerminal}>
              <Plus size={14} />
            </button>
          </div>

          <div className="terminal-output" ref={outputRef}>
            {activeTerminal ? (
              terminals.find((t) => t.id === activeTerminal)?.output || "Terminal ready..."
            ) : (
              <div style={{ color: "var(--text-muted)", padding: "20px", textAlign: "center" }}>
                Click + to open a new terminal
              </div>
            )}
          </div>

          <div className="terminal-input-row">
            <span style={{ color: "var(--accent-cyan)" }}>$</span>
            <input
              className="terminal-input"
              placeholder="Enter command..."
              value={cmdInput}
              onChange={(e) => setCmdInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && runCommand()}
              disabled={!activeTerminal}
            />
            <button className="run-btn" onClick={runCommand} disabled={!activeTerminal}>
              Run
            </button>
          </div>
        </div>
      </div>
    </>
  );
}
