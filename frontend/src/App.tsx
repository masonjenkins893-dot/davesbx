import React, { useState, useEffect } from "react";
import { Dashboard } from "./pages/Dashboard";
import { Logs } from "./pages/Logs";
import { Settings } from "./pages/Settings";
import { LayoutDashboard, ScrollText, Settings as SettingsIcon, TerminalSquare } from "lucide-react";

type Page = "dashboard" | "logs" | "settings";

const API_BASE = "http://localhost:8420";

export const ApiContext = React.createContext({
  baseUrl: API_BASE,
  apiKey: localStorage.getItem("davesbx_api_key") || "",
  setApiKey: (key: string) => {},
});

export default function App() {
  const [page, setPage] = useState<Page>("dashboard");
  const [apiKey, setApiKeyState] = useState(localStorage.getItem("davesbx_api_key") || "");
  const [apiOnline, setApiOnline] = useState(false);

  const setApiKey = (key: string) => {
    localStorage.setItem("davesbx_api_key", key);
    setApiKeyState(key);
  };

  // Check API health
  useEffect(() => {
    const checkHealth = async () => {
      try {
        const res = await fetch(`${API_BASE}/ping`);
        setApiOnline(res.ok);
      } catch {
        setApiOnline(false);
      }
    };
    checkHealth();
    const interval = setInterval(checkHealth, 5000);
    return () => clearInterval(interval);
  }, []);

  const apiContext = { baseUrl: API_BASE, apiKey, setApiKey };

  return (
    <ApiContext.Provider value={apiContext}>
      <div className="app-container">
        {/* Sidebar */}
        <div className="sidebar glass">
          <div className="app-logo">
            <div className="logo-icon">D</div>
            <span className="logo-text">DAVESBX</span>
          </div>

          <div className="nav-item" onClick={() => setPage("dashboard")} style={{ cursor: "pointer" }} className={`nav-item ${page === "dashboard" ? "active" : ""}`}>
            <LayoutDashboard size={18} />
            <span>Dashboard</span>
          </div>

          <div className={`nav-item ${page === "logs" ? "active" : ""}`} onClick={() => setPage("logs")} style={{ cursor: "pointer" }}>
            <ScrollText size={18} />
            <span>Logs</span>
          </div>

          <div className={`nav-item ${page === "settings" ? "active" : ""}`} onClick={() => setPage("settings")} style={{ cursor: "pointer" }}>
            <SettingsIcon size={18} />
            <span>Settings</span>
          </div>

          <div style={{ marginTop: "auto" }}>
            <div className="status-indicator" style={{ padding: "8px 12px" }}>
              <div className={`status-dot ${apiOnline ? "" : "offline"}`}></div>
              <span>{apiOnline ? "API Running" : "API Offline"}</span>
            </div>
          </div>
        </div>

        {/* Main content */}
        <div className="main-content">
          {page === "dashboard" && <Dashboard />}
          {page === "logs" && <Logs />}
          {page === "settings" && <Settings />}
        </div>
      </div>
    </ApiContext.Provider>
  );
}
