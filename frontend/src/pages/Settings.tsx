import React, { useState, useEffect } from "react";
import { ApiContext } from "../App";
import { Globe, HardDrive, Clock, Key, Trash2, RefreshCw } from "lucide-react";

export function Settings() {
  const api = React.useContext(ApiContext);
  const [config, setConfig] = useState<any>({});
  const [saving, setSaving] = useState(false);
  const [storageLimit, setStorageLimit] = useState(10);
  const [timezone, setTimezone] = useState("UTC");
  const [urlMode, setUrlMode] = useState("fastapi");
  const [cloudflare, setCloudflare] = useState({ api_token: "", account_id: "", domain: "", tunnel_mode: "quick" });
  const [supabase, setSupabase] = useState({ access_token: "", project_ref: "", function_name: "davesbx-sandbox" });

  const headers = () => ({ "Content-Type": "application/json", "X-API-Key": api.apiKey });

  useEffect(() => {
    fetch(`${api.baseUrl}/config`, { headers: headers() })
      .then((r) => r.json())
      .then((cfg) => {
        setConfig(cfg);
        setStorageLimit(cfg.storage_limit_gb || 10);
        setTimezone(cfg.timezone || "UTC");
        setUrlMode(cfg.url_mode || "fastapi");
        setCloudflare(cfg.cloudflare || {});
        setSupabase(cfg.supabase || {});
      })
      .catch(() => {});
  }, []);

  const saveSettings = async () => {
    setSaving(true);
    try {
      await fetch(`${api.baseUrl}/config`, {
        method: "POST",
        headers: headers(),
        body: JSON.stringify({
          storage_limit_gb: storageLimit,
          timezone,
          url_mode: urlMode,
          cloudflare,
          supabase,
        }),
      });
    } catch {}
    setSaving(false);
  };

  const regenerateKey = async () => {
    if (!confirm("Regenerate API key? The old key will stop working immediately.")) return;
    try {
      const res = await fetch(`${api.baseUrl}/config/regenerate-key`, {
        method: "POST",
        headers: headers(),
      });
      const data = await res.json();
      if (data.api_key) {
        api.setApiKey(data.api_key);
        alert("New API key generated and saved.");
      }
    } catch {}
  };

  const resetWorkspace = async () => {
    if (!confirm("This will permanently delete ALL files in the workspace. Continue?")) return;
    if (!confirm("Are you absolutely sure? This cannot be undone.")) return;
    try {
      await fetch(`${api.baseUrl}/reset`, { method: "POST", headers: headers() });
      alert("Workspace reset complete.");
    } catch {}
  };

  return (
    <div className="settings-container">
      {/* Public URL Mode */}
      <div className="settings-section glass">
        <h3><Globe size={16} /> Public URL Mode</h3>
        <div className="mode-selector">
          <div className={`mode-option ${urlMode === "fastapi" ? "active" : ""}`} onClick={() => setUrlMode("fastapi")}>
            FastAPI (Default)
          </div>
          <div className={`mode-option ${urlMode === "cloudflare" ? "active" : ""}`} onClick={() => setUrlMode("cloudflare")}>
            Cloudflare Tunnel
          </div>
          <div className={`mode-option ${urlMode === "supabase" ? "active" : ""}`} onClick={() => setUrlMode("supabase")}>
            Supabase Edge
          </div>
        </div>

        {urlMode === "cloudflare" && (
          <div style={{ marginTop: "16px" }}>
            <div className="settings-row">
              <label>Cloudflare API Token</label>
              <input
                className="settings-input"
                type="password"
                value={cloudflare.api_token || ""}
                onChange={(e) => setCloudflare({ ...cloudflare, api_token: e.target.value })}
                placeholder="CF API token"
              />
            </div>
            <div className="settings-row">
              <label>Account ID</label>
              <input
                className="settings-input"
                value={cloudflare.account_id || ""}
                onChange={(e) => setCloudflare({ ...cloudflare, account_id: e.target.value })}
                placeholder="Account ID"
              />
            </div>
            <div className="settings-row">
              <label>Domain</label>
              <input
                className="settings-input"
                value={cloudflare.domain || ""}
                onChange={(e) => setCloudflare({ ...cloudflare, domain: e.target.value })}
                placeholder="yourdomain.com"
              />
            </div>
            <div className="settings-row">
              <label>Tunnel Mode</label>
              <select
                className="settings-select"
                value={cloudflare.tunnel_mode || "quick"}
                onChange={(e) => setCloudflare({ ...cloudflare, tunnel_mode: e.target.value })}
              >
                <option value="quick">Quick (free, random URL)</option>
                <option value="named">Named (custom subdomain)</option>
              </select>
            </div>
          </div>
        )}

        {urlMode === "supabase" && (
          <div style={{ marginTop: "16px" }}>
            <div className="settings-row">
              <label>Supabase Access Token</label>
              <input
                className="settings-input"
                type="password"
                value={supabase.access_token || ""}
                onChange={(e) => setSupabase({ ...supabase, access_token: e.target.value })}
                placeholder="Supabase access token"
              />
            </div>
            <div className="settings-row">
              <label>Project Ref / ID</label>
              <input
                className="settings-input"
                value={supabase.project_ref || ""}
                onChange={(e) => setSupabase({ ...supabase, project_ref: e.target.value })}
                placeholder="project-ref"
              />
            </div>
            <div className="settings-row">
              <label>Function Name</label>
              <input
                className="settings-input"
                value={supabase.function_name || ""}
                onChange={(e) => setSupabase({ ...supabase, function_name: e.target.value })}
                placeholder="davesbx-sandbox"
              />
            </div>
          </div>
        )}
      </div>

      {/* Storage */}
      <div className="settings-section glass">
        <h3><HardDrive size={16} /> Workspace Storage</h3>
        <div className="settings-row">
          <label>Storage Limit (GB)</label>
          <input
            className="settings-input"
            type="number"
            min="0.1"
            step="0.5"
            value={storageLimit}
            onChange={(e) => setStorageLimit(parseFloat(e.target.value))}
          />
        </div>
      </div>

      {/* Timezone */}
      <div className="settings-section glass">
        <h3><Clock size={16} /> Time</h3>
        <div className="settings-row">
          <label>Timezone</label>
          <input
            className="settings-input"
            value={timezone}
            onChange={(e) => setTimezone(e.target.value)}
            placeholder="UTC, America/New_York, Europe/London..."
          />
        </div>
      </div>

      {/* API Key */}
      <div className="settings-section glass">
        <h3><Key size={16} /> API Key</h3>
        <div className="settings-row">
          <label>Current Key</label>
          <input
            className="settings-input"
            type="password"
            value={api.apiKey}
            readOnly
          />
          <button className="settings-btn" onClick={regenerateKey}>
            <RefreshCw size={14} style={{ marginRight: 4, display: "inline" }} />
            Regenerate
          </button>
        </div>
      </div>

      {/* Danger Zone */}
      <div className="settings-section glass">
        <h3><Trash2 size={16} /> Danger Zone</h3>
        <div className="settings-row">
          <label>Reset Workspace</label>
          <button className="settings-btn danger" onClick={resetWorkspace}>
            <Trash2 size={14} style={{ marginRight: 4, display: "inline" }} />
            Delete All Files
          </button>
        </div>
      </div>

      {/* Save button */}
      <button className="settings-btn" onClick={saveSettings} disabled={saving} style={{ alignSelf: "flex-start" }}>
        {saving ? "Saving..." : "Save Settings"}
      </button>
    </div>
  );
}
