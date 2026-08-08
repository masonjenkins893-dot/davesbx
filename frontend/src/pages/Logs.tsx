import React, { useState, useEffect, useRef } from "react";
import { ApiContext } from "../App";
import { Search, AlertCircle } from "lucide-react";

export function Logs() {
  const api = React.useContext(ApiContext);
  const [logs, setLogs] = useState<any[]>([]);
  const [errors, setErrors] = useState<any[]>([]);
  const [showErrorsOnly, setShowErrorsOnly] = useState(false);
  const [searchQuery, setSearchQuery] = useState("");
  const [loading, setLoading] = useState(false);

  const headers = () => ({ "X-API-Key": api.apiKey });

  const fetchLogs = async () => {
    setLoading(true);
    try {
      const [logRes, errRes] = await Promise.all([
        fetch(`${api.baseUrl}/logs?limit=500`, { headers: headers() }),
        fetch(`${api.baseUrl}/logs/errors?limit=200`, { headers: headers() }),
      ]);
      if (logRes.ok) {
        const data = await logRes.json();
        setLogs(data.logs || []);
      }
      if (errRes.ok) {
        const data = await errRes.json();
        setErrors(data.errors || []);
      }
    } catch {}
    setLoading(false);
  };

  useEffect(() => {
    fetchLogs();
    const interval = setInterval(fetchLogs, 10000);
    return () => clearInterval(interval);
  }, []);

  const displayed = showErrorsOnly
    ? errors
    : logs.filter(
        (l) =>
          !searchQuery ||
          l.message?.toLowerCase().includes(searchQuery.toLowerCase()) ||
          JSON.stringify(l.details || {}).toLowerCase().includes(searchQuery.toLowerCase())
      );

  return (
    <div className="logs-container glass">
      <div className="logs-header">
        <input
          className="log-search glass"
          placeholder="Search logs..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
        />
        <div
          className={`mode-option ${!showErrorsOnly ? "active" : ""}`}
          onClick={() => setShowErrorsOnly(false)}
          style={{ minWidth: "100px" }}
        >
          All Logs
        </div>
        <div
          className={`mode-option ${showErrorsOnly ? "active" : ""}`}
          onClick={() => setShowErrorsOnly(true)}
          style={{ minWidth: "100px" }}
        >
          <AlertCircle size={14} style={{ display: "inline", marginRight: 4 }} />
          Errors ({errors.length})
        </div>
      </div>

      <div className="logs-list">
        {loading && displayed.length === 0 ? (
          <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
            Loading logs...
          </div>
        ) : displayed.length === 0 ? (
          <div style={{ padding: "20px", textAlign: "center", color: "var(--text-muted)", fontSize: "13px" }}>
            No logs yet
          </div>
        ) : (
          displayed.map((entry, i) => (
            <div key={i} className={`log-entry ${entry.type === "error" ? "error" : ""}`}>
              <span className="log-timestamp">
                {entry.timestamp ? new Date(entry.timestamp).toLocaleTimeString() : "--:--:--"}
              </span>
              <span className={`log-type ${entry.type || "system"}`}>{entry.type || "system"}</span>
              <span className="log-message">{entry.message}</span>
            </div>
          ))
        )}
      </div>
    </div>
  );
}
