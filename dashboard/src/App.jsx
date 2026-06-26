import React, { useState, useEffect, useRef } from 'react';

const API_BASE = 'http://127.0.0.1:8000';

export default function App() {
  const [activeTab, setActiveTab] = useState('home');
  const [stats, setStats] = useState(null);
  const [backendOnline, setBackendOnline] = useState(false);
  const [config, setConfig] = useState(null);
  const [providers, setProviders] = useState([]);
  const [tools, setTools] = useState([]);
  const [memory, setMemory] = useState({ locations: {}, notes: {}, preferences: {} });
  const [logs, setLogs] = useState([]);
  const [logFilter, setLogFilter] = useState({ source: '', level: '', category: '', query: '' });
  const [saveLoading, setSaveLoading] = useState(false);
  const [toast, setToast] = useState(null);
  const [apiKeysVisible, setApiKeysVisible] = useState(false);
  const [logsAutoRefresh, setLogsAutoRefresh] = useState(true);

  // Modal/Form States for Adding Memory
  const [showAddMem, setShowAddMem] = useState(null); // 'location', 'note', 'preference'
  const [newLoc, setNewLoc] = useState({ name: '', x: 0, y: 64, z: 0, dimension: 'minecraft:overworld', biome: 'minecraft:plains' });
  const [newNote, setNewNote] = useState({ key: '', value: '' });
  const [newPref, setNewPref] = useState({ key: '', value: '' });

  // Inline editing states
  const [editingLoc, setEditingLoc] = useState(null);
  const [editingNote, setEditingNote] = useState(null);
  const [editingPref, setEditingPref] = useState(null);

  // Poll stats and check backend status
  useEffect(() => {
    const fetchStats = async () => {
      try {
        const res = await fetch(`${API_BASE}/api/resources/stats`);
        if (res.ok) {
          const data = await res.json();
          setStats(data);
          setBackendOnline(true);
        } else {
          setBackendOnline(false);
        }
      } catch (err) {
        setBackendOnline(false);
      }
    };

    fetchStats();
    const interval = setInterval(fetchStats, 2000);
    return () => clearInterval(interval);
  }, []);

  // Fetch initial data
  useEffect(() => {
    if (backendOnline) {
      fetchConfig();
      fetchProviders();
      fetchTools();
      fetchMemory();
      fetchLogs();
    }
  }, [backendOnline]);

  // Poll logs if auto-refresh is active
  useEffect(() => {
    if (!backendOnline || !logsAutoRefresh) return;
    
    const interval = setInterval(fetchLogs, 3000);
    return () => clearInterval(interval);
  }, [backendOnline, logsAutoRefresh, logFilter]);

  const showToast = (message, type = 'success') => {
    setToast({ message, type });
    setTimeout(() => setToast(null), 3000);
  };

  const fetchConfig = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/config`);
      if (res.ok) {
        const data = await res.json();
        setConfig(data);
      }
    } catch (err) {
      console.error('Failed to fetch config', err);
    }
  };

  const fetchProviders = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/providers`);
      if (res.ok) {
        const data = await res.json();
        setProviders(data);
      }
    } catch (err) {
      console.error('Failed to fetch providers', err);
    }
  };

  const fetchTools = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/tools`);
      if (res.ok) {
        const data = await res.json();
        setTools(data);
      }
    } catch (err) {
      console.error('Failed to fetch tools', err);
    }
  };

  const fetchMemory = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/memory`);
      if (res.ok) {
        const data = await res.json();
        setMemory(data);
      }
    } catch (err) {
      console.error('Failed to fetch memory', err);
    }
  };

  const fetchLogs = async () => {
    try {
      const queryParams = new URLSearchParams();
      if (logFilter.source) queryParams.append('source', logFilter.source);
      if (logFilter.level) queryParams.append('level', logFilter.level);
      if (logFilter.category) queryParams.append('category', logFilter.category);
      if (logFilter.query) queryParams.append('query', logFilter.query);
      queryParams.append('limit', '100');

      const res = await fetch(`${API_BASE}/api/logs?${queryParams.toString()}`);
      if (res.ok) {
        const data = await res.json();
        setLogs(data);
      }
    } catch (err) {
      console.error('Failed to fetch logs', err);
    }
  };

  const handleSaveConfig = async (e) => {
    e.preventDefault();
    setSaveLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/config`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(config)
      });
      if (res.ok) {
        showToast('Configuration saved successfully!');
        fetchConfig();
        fetchProviders(); // Refresh availability in case key changed
      } else {
        const err = await res.json();
        showToast(`Failed to save config: ${err.detail || 'Error'}`, 'error');
      }
    } catch (err) {
      showToast('Error saving configuration.', 'error');
    } finally {
      setSaveLoading(false);
    }
  };

  // Memory Actions
  const handleAddMemory = async (type) => {
    let endpoint = '';
    let body = {};
    let keyName = '';

    if (type === 'location') {
      endpoint = `/api/memory/locations/${newLoc.name}`;
      body = {
        x: Number(newLoc.x),
        y: Number(newLoc.y),
        z: Number(newLoc.z),
        dimension: newLoc.dimension,
        biome: newLoc.biome,
        timestamp: new Date().toISOString()
      };
      keyName = newLoc.name;
    } else if (type === 'note') {
      endpoint = `/api/memory/notes/${newNote.key}`;
      body = { value: newNote.value };
      keyName = newNote.key;
    } else if (type === 'preference') {
      endpoint = `/api/memory/preferences/${newPref.key}`;
      body = { value: newPref.value };
      keyName = newPref.key;
    }

    if (!keyName.trim()) {
      showToast('Name/Key cannot be empty', 'error');
      return;
    }

    try {
      const res = await fetch(`${API_BASE}${endpoint}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body)
      });
      if (res.ok) {
        showToast('Memory entry added!');
        setShowAddMem(null);
        fetchMemory();
        // Reset states
        setNewLoc({ name: '', x: 0, y: 64, z: 0, dimension: 'minecraft:overworld', biome: 'minecraft:plains' });
        setNewNote({ key: '', value: '' });
        setNewPref({ key: '', value: '' });
      } else {
        showToast('Failed to add memory entry', 'error');
      }
    } catch (err) {
      showToast('Error adding memory entry', 'error');
    }
  };

  const handleDeleteMemory = async (type, key) => {
    if (!confirm(`Are you sure you want to delete this ${type}?`)) return;
    try {
      const res = await fetch(`${API_BASE}/api/memory/${type}s/${key}`, {
        method: 'DELETE'
      });
      if (res.ok) {
        showToast('Memory entry deleted!');
        fetchMemory();
      } else {
        showToast('Failed to delete entry', 'error');
      }
    } catch (err) {
      showToast('Error deleting entry', 'error');
    }
  };

  const handleEditMemory = async (type, key, data) => {
    try {
      const res = await fetch(`${API_BASE}/api/memory/${type}s/${key}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
      });
      if (res.ok) {
        showToast('Memory entry updated!');
        setEditingLoc(null);
        setEditingNote(null);
        setEditingPref(null);
        fetchMemory();
      } else {
        showToast('Failed to update entry', 'error');
      }
    } catch (err) {
      showToast('Error updating entry', 'error');
    }
  };

  const formatUptime = (sec) => {
    if (!sec) return '0s';
    const hrs = Math.floor(sec / 3600);
    const mins = Math.floor((sec % 3600) / 60);
    const secs = sec % 60;
    
    let parts = [];
    if (hrs > 0) parts.push(`${hrs}h`);
    if (mins > 0) parts.push(`${mins}m`);
    parts.push(`${secs}s`);
    return parts.join(' ');
  };

  const handleApplyFilter = (key, val) => {
    const updated = { ...logFilter, [key]: val };
    setLogFilter(updated);
    // Trigger immediate logs refresh
    setTimeout(() => {
      fetchLogs();
    }, 50);
  };

  // Render Functions for Tabs
  const renderHome = () => {
    if (!stats) return <div style={{ color: 'var(--color-text-secondary)' }}>Loading telemetry...</div>;

    const cards = [
      { title: 'Current Provider', value: stats.current_provider, footer: `Model: ${stats.current_model}` },
      { title: 'Launcher Status', value: stats.launcher_status, footer: stats.launcher_status === 'Active (Connected)' ? 'Connected to tray' : 'Offline / monitoring' },
      { title: 'Requests Today', value: stats.requests_today, footer: `Session: ${stats.requests_session}` },
      { title: 'Remaining Quota', value: stats.remaining_quota, footer: 'Daily requests left' },
      { title: 'Token Usage Today', value: stats.total_tokens_today.toLocaleString(), footer: `In: ${stats.input_tokens_today.toLocaleString()} | Out: ${stats.output_tokens_today.toLocaleString()}` },
      { title: 'Average Latency', value: `${stats.average_latency}s`, footer: `Failed: ${stats.failed_requests}` },
      { title: 'Backend Uptime', value: formatUptime(stats.backend_uptime), footer: `Started: ${new Date(Date.now() - stats.backend_uptime * 1000).toLocaleTimeString()}` },
      { title: 'AI Status', value: backendOnline ? 'Healthy' : 'Disconnected', footer: 'API connection status' }
    ];

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div className="stats-grid">
          {cards.map((c, i) => (
            <div key={i} className="card">
              <div className="card-title">{c.title}</div>
              <div className="card-value" style={c.title === 'Launcher Status' && stats.launcher_status === 'Active (Connected)' ? {color: 'var(--color-green)'} : {}}>
                {c.value}
              </div>
              <div className="card-footer">{c.footer}</div>
            </div>
          ))}
        </div>

        <div className="form-section">
          <div className="form-title">Recent Assistant Events</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {logs.slice(0, 6).map((log, i) => (
              <div key={i} style={{ display: 'flex', gap: '16px', fontSize: '14px', borderBottom: '1px solid #1a1a1a', paddingBottom: '8px' }}>
                <span style={{ color: '#555' }}>{log.timestamp}</span>
                <span className={`log-source ${log.source}`} style={{ width: '70px', fontWeight: 'bold' }}>{log.source.toUpperCase()}</span>
                <span className={`log-level ${log.level.toLowerCase()}`} style={{ width: '60px', fontWeight: 'bold' }}>{log.level}</span>
                <span style={{ color: '#eee', flexGrow: 1 }}>{log.message}</span>
              </div>
            ))}
            {logs.length === 0 && <div style={{ color: 'var(--color-text-secondary)' }}>No recent logs.</div>}
          </div>
        </div>
      </div>
    );
  };

  const renderConfig = () => {
    if (!config) return <div style={{ color: 'var(--color-text-secondary)' }}>Loading configuration...</div>;

    const currentProviderData = providers.find(p => p.id === config.provider);
    const models = currentProviderData ? currentProviderData.models : [];

    const handleLimitChange = (key, val) => {
      const updatedLimits = { ...config.rate_limits };
      if (!updatedLimits[config.provider]) {
        updatedLimits[config.provider] = {};
      }
      updatedLimits[config.provider][key] = Number(val);
      setConfig({ ...config, rate_limits: updatedLimits });
    };

    const currentLimits = config.rate_limits?.[config.provider] || {
      requests_per_minute: 15,
      tokens_per_minute: 1000000,
      requests_per_day: 1500
    };

    return (
      <form onSubmit={handleSaveConfig} className="form-section">
        <div className="form-title">AI Engine Settings</div>
        
        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Active Provider</label>
            <select 
              className="form-select"
              value={config.provider}
              onChange={(e) => setConfig({ ...config, provider: e.target.value, model: providers.find(p => p.id === e.target.value)?.default_model || '' })}
            >
              {providers.map(p => (
                <option key={p.id} value={p.id}>{p.name} {!p.available && p.id === 'gemini' ? '(API Key Missing)' : ''}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Model Selection</label>
            {models.length > 0 ? (
              <select 
                className="form-select"
                value={config.model}
                onChange={(e) => setConfig({ ...config, model: e.target.value })}
              >
                {models.map(m => (
                  <option key={m} value={m}>{m}</option>
                ))}
              </select>
            ) : (
              <input 
                type="text" 
                className="form-input"
                value={config.model}
                onChange={(e) => setConfig({ ...config, model: e.target.value })}
              />
            )}
          </div>

          <div className="form-group">
            <label className="form-label">Gemini API Key</label>
            <div style={{ display: 'flex', gap: '8px' }}>
              <input 
                type={apiKeysVisible ? "text" : "password"}
                className="form-input" 
                style={{ flexGrow: 1 }}
                value={config.gemini_api_key}
                onChange={(e) => setConfig({ ...config, gemini_api_key: e.target.value })}
                placeholder="Enter Gemini API Key"
              />
              <button 
                type="button" 
                className="btn btn-secondary"
                onClick={() => setApiKeysVisible(!apiKeysVisible)}
              >
                {apiKeysVisible ? "Hide" : "Show"}
              </button>
            </div>
            <span style={{ fontSize: '11px', color: '#666' }}>API Key is stored securely in backend/.env file and never logged.</span>
          </div>

          <div className="form-group">
            <label className="form-label">Timeout (seconds)</label>
            <input 
              type="number" 
              className="form-input"
              value={config.timeout}
              onChange={(e) => setConfig({ ...config, timeout: Number(e.target.value) })}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Temperature: {config.temperature}</label>
            <input 
              type="range" 
              min="0" 
              max="2" 
              step="0.1" 
              value={config.temperature}
              onChange={(e) => setConfig({ ...config, temperature: parseFloat(e.target.value) })}
              style={{ accentColor: 'var(--color-green)' }}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Max Generation Tokens</label>
            <input 
              type="number" 
              className="form-input"
              value={config.max_tokens}
              onChange={(e) => setConfig({ ...config, max_tokens: Number(e.target.value) })}
            />
          </div>
        </div>

        <div className="form-title" style={{ marginTop: '20px' }}>Rate Limit Policies ({config.provider.toUpperCase()})</div>
        <div className="form-grid">
          <div className="form-group">
            <label className="form-label">Requests Per Minute (RPM)</label>
            <input 
              type="number" 
              className="form-input"
              value={currentLimits.requests_per_minute}
              onChange={(e) => handleLimitChange('requests_per_minute', e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Tokens Per Minute (TPM)</label>
            <input 
              type="number" 
              className="form-input"
              value={currentLimits.tokens_per_minute}
              onChange={(e) => handleLimitChange('tokens_per_minute', e.target.value)}
            />
          </div>

          <div className="form-group">
            <label className="form-label">Requests Per Day (RPD)</label>
            <input 
              type="number" 
              className="form-input"
              value={currentLimits.requests_per_day}
              onChange={(e) => handleLimitChange('requests_per_day', e.target.value)}
            />
          </div>
        </div>

        <button type="submit" className="btn" disabled={saveLoading} style={{ marginTop: '20px' }}>
          {saveLoading ? 'Saving...' : 'Save Configuration'}
        </button>
      </form>
    );
  };

  const renderResources = () => {
    if (!stats) return <div style={{ color: 'var(--color-text-secondary)' }}>Loading statistics...</div>;

    // Custom SVG Line Chart for Weekly token usage
    const weeklyData = stats.weekly_history || [];
    const maxTokensVal = Math.max(...weeklyData.map(d => d.tokens), 100);
    const chartWidth = 500;
    const chartHeight = 150;
    const points = weeklyData.map((d, i) => {
      const x = (i / (weeklyData.length - 1)) * (chartWidth - 60) + 40;
      const y = chartHeight - 20 - (d.tokens / maxTokensVal) * (chartHeight - 40);
      return { x, y, label: d.date, value: d.tokens };
    });

    const pathD = points.length > 0 
      ? `M ${points[0].x} ${points[0].y} ` + points.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ')
      : '';
      
    const areaD = points.length > 0 
      ? `${pathD} L ${points[points.length-1].x} ${chartHeight - 20} L ${points[0].x} ${chartHeight - 20} Z`
      : '';

    // Custom SVG Latency chart for last 10 requests
    const recentReqs = (stats.recent_requests || []).slice(0, 10).reverse();
    const maxLatencyVal = Math.max(...recentReqs.map(r => r.latency), 1);
    const latencyPoints = recentReqs.map((r, i) => {
      const x = (i / Math.max(1, recentReqs.length - 1)) * (chartWidth - 60) + 40;
      const y = chartHeight - 20 - (r.latency / maxLatencyVal) * (chartHeight - 40);
      return { x, y, value: r.latency };
    });
    
    const latencyPathD = latencyPoints.length > 0
      ? `M ${latencyPoints[0].x} ${latencyPoints[0].y} ` + latencyPoints.slice(1).map(p => `L ${p.x} ${p.y}`).join(' ')
      : '';

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          
          {/* Weekly Token Usage Chart */}
          <div className="chart-container">
            <div className="chart-title">Token Usage (Last 7 Days)</div>
            <div style={{ flexGrow: 1, position: 'relative' }}>
              <svg className="svg-chart" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none">
                <defs>
                  <linearGradient id="chart-gradient" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="0%" stopColor="var(--color-green)" stopOpacity="0.4" />
                    <stop offset="100%" stopColor="var(--color-green)" stopOpacity="0.0" />
                  </linearGradient>
                </defs>
                {/* Gridlines */}
                <line x1="40" y1="20" x2={chartWidth - 20} y2="20" className="chart-grid" />
                <line x1="40" y1="65" x2={chartWidth - 20} y2="65" className="chart-grid" />
                <line x1="40" y1="110" x2={chartWidth - 20} y2="110" className="chart-grid" />
                <line x1="40" y1={chartHeight - 20} x2={chartWidth - 20} y2={chartHeight - 20} stroke="#444" strokeWidth="1.5" />
                
                {/* Area under curve */}
                {points.length > 0 && <path d={areaD} className="chart-area" />}
                
                {/* Line Curve */}
                {points.length > 0 && <path d={pathD} className="chart-line" />}
                
                {/* Dots & Labels */}
                {points.map((p, i) => (
                  <g key={i}>
                    <circle cx={p.x} cy={p.y} r="5" className="chart-dot" />
                    <text x={p.x} y={chartHeight - 5} textAnchor="middle" className="chart-label">{p.label.split('-')[2]}</text>
                    <text x={p.x} y={p.y - 8} textAnchor="middle" className="chart-label" style={{fill: '#eee', fontSize: '9px'}}>{p.value > 1000 ? `${(p.value/1000).toFixed(1)}k` : p.value}</text>
                  </g>
                ))}
              </svg>
            </div>
          </div>

          {/* Latency History Chart */}
          <div className="chart-container">
            <div className="chart-title">Request Latency (Seconds, Last 10)</div>
            <div style={{ flexGrow: 1, position: 'relative' }}>
              <svg className="svg-chart" viewBox={`0 0 ${chartWidth} ${chartHeight}`} preserveAspectRatio="none">
                <line x1="40" y1="20" x2={chartWidth - 20} y2="20" className="chart-grid" />
                <line x1="40" y1="65" x2={chartWidth - 20} y2="65" className="chart-grid" />
                <line x1="40" y1="110" x2={chartWidth - 20} y2="110" className="chart-grid" />
                <line x1="40" y1={chartHeight - 20} x2={chartWidth - 20} y2={chartHeight - 20} stroke="#444" strokeWidth="1.5" />
                
                {latencyPoints.length > 0 && <path d={latencyPathD} className="chart-line" style={{stroke: '#5555ff'}} />}
                {latencyPoints.map((p, i) => (
                  <g key={i}>
                    <circle cx={p.x} cy={p.y} r="5" className="chart-dot" style={{fill: '#5555ff'}} />
                    <text x={p.x} y={p.y - 8} textAnchor="middle" className="chart-label" style={{fill: '#eee', fontSize: '9px'}}>{p.value}s</text>
                  </g>
                ))}
                {latencyPoints.length === 0 && (
                  <text x={chartWidth/2} y={chartHeight/2} textAnchor="middle" fill="#555">No request data yet</text>
                )}
              </svg>
            </div>
          </div>

        </div>

        {/* Detailed Requests History Table */}
        <div className="form-section">
          <div className="form-title">Recent Request Telemetry Log</div>
          <table style={{ width: '100%', borderCollapse: 'collapse', marginTop: '10px' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #222', textAlign: 'left', color: 'var(--color-text-secondary)', fontSize: '13px' }}>
                <th style={{ padding: '12px' }}>Timestamp</th>
                <th style={{ padding: '12px' }}>Provider</th>
                <th style={{ padding: '12px' }}>Model</th>
                <th style={{ padding: '12px' }}>Tokens (In/Out)</th>
                <th style={{ padding: '12px' }}>Latency</th>
                <th style={{ padding: '12px' }}>Status</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_requests.map((r, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #1a1a1a', fontSize: '14px' }}>
                  <td style={{ padding: '12px', color: '#888' }}>{new Date(r.timestamp).toLocaleTimeString()}</td>
                  <td style={{ padding: '12px', fontWeight: '500' }}>{r.provider}</td>
                  <td style={{ padding: '12px', color: '#ccc' }}>{r.model}</td>
                  <td style={{ padding: '12px' }}>{r.input_tokens + r.output_tokens} <span style={{fontSize: '11px', color: '#666'}}>({r.input_tokens} / {r.output_tokens})</span></td>
                  <td style={{ padding: '12px' }}>{r.latency}s {r.is_retry && <span style={{fontSize: '11px', color: 'var(--color-warning)'}}>(Retried)</span>}</td>
                  <td style={{ padding: '12px' }}>
                    <span style={{ 
                      padding: '2px 8px', 
                      borderRadius: '10px', 
                      fontSize: '12px', 
                      fontWeight: 'bold', 
                      backgroundColor: r.success ? 'rgba(60, 200, 60, 0.1)' : 'rgba(255, 85, 85, 0.1)',
                      color: r.success ? 'var(--color-green)' : 'var(--color-error)'
                    }}>
                      {r.success ? 'Success' : 'Failed'}
                    </span>
                  </td>
                </tr>
              ))}
              {stats.recent_requests.length === 0 && (
                <tr>
                  <td colSpan="6" style={{ padding: '20px', textAlign: 'center', color: '#666' }}>No requests recorded yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderMemory = () => {
    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        
        {/* Locations Section */}
        <div className="form-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div className="form-title" style={{border: 'none', padding: '0'}}>Saved Locations</div>
            <button className="btn" onClick={() => setShowAddMem('location')}>+ Add Location</button>
          </div>

          <div className="memory-grid" style={{ marginTop: '16px' }}>
            {Object.entries(memory.locations || {}).map(([name, loc]) => (
              <div key={name} className="memory-item">
                {editingLoc === name ? (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                    <input 
                      type="text" 
                      className="form-input" 
                      value={name} 
                      disabled
                    />
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <input type="number" placeholder="X" className="form-input" style={{width: '33%'}} value={loc.x} onChange={(e) => setMemory({ ...memory, locations: { ...memory.locations, [name]: { ...loc, x: Number(e.target.value) } } })} />
                      <input type="number" placeholder="Y" className="form-input" style={{width: '33%'}} value={loc.y} onChange={(e) => setMemory({ ...memory, locations: { ...memory.locations, [name]: { ...loc, y: Number(e.target.value) } } })} />
                      <input type="number" placeholder="Z" className="form-input" style={{width: '33%'}} value={loc.z} onChange={(e) => setMemory({ ...memory, locations: { ...memory.locations, [name]: { ...loc, z: Number(e.target.value) } } })} />
                    </div>
                    <input type="text" placeholder="Dimension" className="form-input" value={loc.dimension} onChange={(e) => setMemory({ ...memory, locations: { ...memory.locations, [name]: { ...loc, dimension: e.target.value } } })} />
                    <input type="text" placeholder="Biome" className="form-input" value={loc.biome} onChange={(e) => setMemory({ ...memory, locations: { ...memory.locations, [name]: { ...loc, biome: e.target.value } } })} />
                    <div className="memory-actions">
                      <button className="btn" onClick={() => handleEditMemory('location', name, loc)}>Save</button>
                      <button className="btn btn-secondary" onClick={() => setEditingLoc(null)}>Cancel</button>
                    </div>
                  </div>
                ) : (
                  <>
                    <div className="memory-header">
                      <span className="memory-title">{name}</span>
                      <span className="status-indicator active" style={{fontSize: '11px', padding: '2px 8px'}}>{loc.dimension.split(':').pop().toUpperCase()}</span>
                    </div>
                    <div className="memory-details">
                      <div className="memory-coord">
                        <span>X: <b>{loc.x.toFixed(1)}</b></span>
                        <span>Y: <b>{loc.y.toFixed(1)}</b></span>
                        <span>Z: <b>{loc.z.toFixed(1)}</b></span>
                      </div>
                      <div style={{fontSize: '13px', color: '#ccc'}}>Biome: {loc.biome}</div>
                      <span className="memory-meta">Saved: {new Date(loc.timestamp).toLocaleString()}</span>
                    </div>
                    <div className="memory-actions">
                      <button className="btn btn-secondary" style={{padding: '6px 12px', fontSize: '13px'}} onClick={() => setEditingLoc(name)}>Edit</button>
                      <button className="btn btn-danger" style={{padding: '6px 12px', fontSize: '13px'}} onClick={() => handleDeleteMemory('location', name)}>Delete</button>
                    </div>
                  </>
                )}
              </div>
            ))}
            {Object.keys(memory.locations || {}).length === 0 && (
              <div style={{ color: '#666', gridColumn: '1/-1' }}>No saved locations. Use `save_location` in game.</div>
            )}
          </div>
        </div>

        {/* Notes & Preferences Row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          
          {/* Notes */}
          <div className="form-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="form-title" style={{border: 'none', padding: '0'}}>Saved Notes</div>
              <button className="btn" onClick={() => setShowAddMem('note')}>+ Add Note</button>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
              {Object.entries(memory.notes || {}).map(([key, val]) => (
                <div key={key} className="memory-item" style={{gap: '8px'}}>
                  {editingNote === key ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <input type="text" className="form-input" value={key} disabled />
                      <textarea className="form-input" style={{resize: 'vertical', minHeight: '60px'}} value={val} onChange={(e) => setMemory({ ...memory, notes: { ...memory.notes, [key]: e.target.value } })} />
                      <div className="memory-actions">
                        <button className="btn" onClick={() => handleEditMemory('note', key, { value: val })}>Save</button>
                        <button className="btn btn-secondary" onClick={() => setEditingNote(null)}>Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div style={{ fontWeight: 'bold', color: 'var(--color-green)' }}>{key}</div>
                      <div style={{ fontSize: '14px', color: '#eee', whiteSpace: 'pre-wrap' }}>{val}</div>
                      <div className="memory-actions" style={{border: 'none', paddingTop: '0', marginTop: '4px'}}>
                        <button className="btn btn-secondary" style={{padding: '4px 10px', fontSize: '12px'}} onClick={() => setEditingNote(key)}>Edit</button>
                        <button className="btn btn-danger" style={{padding: '4px 10px', fontSize: '12px'}} onClick={() => handleDeleteMemory('note', key)}>Delete</button>
                      </div>
                    </>
                  )}
                </div>
              ))}
              {Object.keys(memory.notes || {}).length === 0 && (
                <div style={{ color: '#666' }}>No notes saved. Use `save_note` in game.</div>
              )}
            </div>
          </div>

          {/* Preferences */}
          <div className="form-section">
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div className="form-title" style={{border: 'none', padding: '0'}}>Preferences</div>
              <button className="btn" onClick={() => setShowAddMem('preference')}>+ Add Pref</button>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
              {Object.entries(memory.preferences || {}).map(([key, val]) => (
                <div key={key} className="memory-item" style={{gap: '8px'}}>
                  {editingPref === key ? (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                      <input type="text" className="form-input" value={key} disabled />
                      <input type="text" className="form-input" value={val} onChange={(e) => setMemory({ ...memory, preferences: { ...memory.preferences, [key]: e.target.value } })} />
                      <div className="memory-actions">
                        <button className="btn" onClick={() => handleEditMemory('preference', key, { value: val })}>Save</button>
                        <button className="btn btn-secondary" onClick={() => setEditingPref(null)}>Cancel</button>
                      </div>
                    </div>
                  ) : (
                    <>
                      <div style={{ fontWeight: 'bold', color: 'var(--color-green)' }}>{key}</div>
                      <div style={{ fontSize: '14px', color: '#eee' }}>{val}</div>
                      <div className="memory-actions" style={{border: 'none', paddingTop: '0', marginTop: '4px'}}>
                        <button className="btn btn-secondary" style={{padding: '4px 10px', fontSize: '12px'}} onClick={() => setEditingPref(key)}>Edit</button>
                        <button className="btn btn-danger" style={{padding: '4px 10px', fontSize: '12px'}} onClick={() => handleDeleteMemory('preference', key)}>Delete</button>
                      </div>
                    </>
                  )}
                </div>
              ))}
              {Object.keys(memory.preferences || {}).length === 0 && (
                <div style={{ color: '#666' }}>No preferences saved.</div>
              )}
            </div>
          </div>

        </div>

        {/* Modal for adding memory */}
        {showAddMem && (
          <div style={{
            position: 'fixed', top: 0, left: 0, right: 0, bottom: 0, 
            backgroundColor: 'rgba(0,0,0,0.8)', display: 'flex', 
            justifyContent: 'center', alignItems: 'center', zIndex: 1000
          }}>
            <div className="form-section" style={{ width: '450px', border: '2px solid var(--color-green)' }}>
              <div className="form-title">Add New {showAddMem.toUpperCase()}</div>
              
              {showAddMem === 'location' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Location Name</label>
                    <input type="text" className="form-input" value={newLoc.name} onChange={(e) => setNewLoc({...newLoc, name: e.target.value})} placeholder="e.g. Diamond Cave" />
                  </div>
                  <div style={{ display: 'flex', gap: '8px' }}>
                    <div className="form-group" style={{width: '33%'}}><label className="form-label">X</label><input type="number" className="form-input" value={newLoc.x} onChange={(e) => setNewLoc({...newLoc, x: Number(e.target.value)})} /></div>
                    <div className="form-group" style={{width: '33%'}}><label className="form-label">Y</label><input type="number" className="form-input" value={newLoc.y} onChange={(e) => setNewLoc({...newLoc, y: Number(e.target.value)})} /></div>
                    <div className="form-group" style={{width: '33%'}}><label className="form-label">Z</label><input type="number" className="form-input" value={newLoc.z} onChange={(e) => setNewLoc({...newLoc, z: Number(e.target.value)})} /></div>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Dimension</label>
                    <select className="form-select" value={newLoc.dimension} onChange={(e) => setNewLoc({...newLoc, dimension: e.target.value})}>
                      <option value="minecraft:overworld">Overworld</option>
                      <option value="minecraft:the_nether">The Nether</option>
                      <option value="minecraft:the_end">The End</option>
                    </select>
                  </div>
                  <div className="form-group">
                    <label className="form-label">Biome</label>
                    <input type="text" className="form-input" value={newLoc.biome} onChange={(e) => setNewLoc({...newLoc, biome: e.target.value})} />
                  </div>
                </div>
              )}

              {showAddMem === 'note' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Note Key</label>
                    <input type="text" className="form-input" value={newNote.key} onChange={(e) => setNewNote({...newNote, key: e.target.value})} placeholder="e.g. village_trade" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Content</label>
                    <textarea className="form-input" style={{minHeight: '80px'}} value={newNote.value} onChange={(e) => setNewNote({...newNote, value: e.target.value})} placeholder="Enter note details..." />
                  </div>
                </div>
              )}

              {showAddMem === 'preference' && (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
                  <div className="form-group">
                    <label className="form-label">Preference Key</label>
                    <input type="text" className="form-input" value={newPref.key} onChange={(e) => setNewPref({...newPref, key: e.target.value})} placeholder="e.g. favorite_weapon" />
                  </div>
                  <div className="form-group">
                    <label className="form-label">Value</label>
                    <input type="text" className="form-input" value={newPref.value} onChange={(e) => setNewPref({...newPref, value: e.target.value})} placeholder="e.g. diamond_axe" />
                  </div>
                </div>
              )}

              <div style={{ display: 'flex', gap: '12px', marginTop: '16px' }}>
                <button className="btn" onClick={() => handleAddMemory(showAddMem)}>Add Entry</button>
                <button className="btn btn-secondary" onClick={() => setShowAddMem(null)}>Cancel</button>
              </div>
            </div>
          </div>
        )}

      </div>
    );
  };

  const renderTools = () => {
    // Group tools by category
    const categories = {
      'Perception Tools': tools.filter(t => t.category === 'Perception'),
      'Memory Tools': tools.filter(t => t.category === 'Memory')
    };

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '32px' }}>
        {Object.entries(categories).map(([catName, catTools]) => (
          <div key={catName} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div className="form-title" style={{ fontSize: '20px', borderBottom: '2px solid #222', paddingBottom: '8px' }}>{catName}</div>
            
            <div className="tools-grid">
              {catTools.map(tool => (
                <div key={tool.name} className="tool-card">
                  <div className="tool-header">
                    <span className="tool-name">{tool.name}</span>
                    <span className="status-indicator active" style={{fontSize: '11px', padding: '2px 8px'}}>{tool.category.toUpperCase()}</span>
                  </div>
                  
                  <div className="tool-desc">{tool.description}</div>
                  
                  <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px', marginTop: '10px' }}>
                    <div className="tool-section">
                      <div className="tool-section-title">Arguments Schema</div>
                      <pre style={{
                        backgroundColor: '#0a0a0a', 
                        padding: '12px', 
                        borderRadius: '6px', 
                        fontSize: '12px', 
                        border: '1px solid #1a1a1a',
                        overflowX: 'auto',
                        fontFamily: 'Consolas, monospace'
                      }}>
                        {JSON.stringify(tool.parameters.properties, null, 2)}
                      </pre>
                    </div>

                    <div className="tool-section">
                      <div className="tool-section-title">Usage Examples</div>
                      <div className="tool-examples">
                        {tool.examples.map((ex, i) => (
                          <div key={i}>"{ex}"</div>
                        ))}
                      </div>
                    </div>
                  </div>
                </div>
              ))}
              {catTools.length === 0 && <div style={{ color: '#555' }}>No tools loaded.</div>}
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderLogs = () => {
    const bottomRef = useRef(null);

    // Scroll logs to bottom when new logs arrive
    useEffect(() => {
      if (bottomRef.current) {
        bottomRef.current.scrollIntoView({ behavior: 'smooth' });
      }
    }, [logs]);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', height: 'calc(100vh - 120px)' }}>
        
        {/* Logs Filter Toolbar */}
        <div className="console-toolbar">
          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: '#888' }}>Source:</span>
            <select className="form-select" style={{padding: '6px 12px'}} value={logFilter.source} onChange={(e) => handleApplyFilter('source', e.target.value)}>
              <option value="">All</option>
              <option value="backend">Backend</option>
              <option value="launcher">Launcher</option>
            </select>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: '#888' }}>Level:</span>
            <select className="form-select" style={{padding: '6px 12px'}} value={logFilter.level} onChange={(e) => handleApplyFilter('level', e.target.value)}>
              <option value="">All</option>
              <option value="INFO">INFO</option>
              <option value="DEBUG">DEBUG</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </select>
          </div>

          <div style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
            <span style={{ fontSize: '13px', color: '#888' }}>Category:</span>
            <select className="form-select" style={{padding: '6px 12px'}} value={logFilter.category} onChange={(e) => handleApplyFilter('category', e.target.value)}>
              <option value="">All</option>
              <option value="Tool Execution">Tool Execution</option>
              <option value="Error">Error</option>
              <option value="General">General</option>
            </select>
          </div>

          <input 
            type="text" 
            className="form-input" 
            placeholder="Search logs..." 
            style={{ padding: '6px 12px', flexGrow: 1, minWidth: '150px' }}
            value={logFilter.query}
            onChange={(e) => handleApplyFilter('query', e.target.value)}
          />

          <button className="btn btn-secondary" style={{padding: '8px 16px', fontSize: '13px'}} onClick={fetchLogs}>Refresh</button>

          <label style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '13px', color: '#888', cursor: 'pointer' }}>
            <input type="checkbox" checked={logsAutoRefresh} onChange={(e) => setLogsAutoRefresh(e.target.checked)} style={{accentColor: 'var(--color-green)'}} />
            Auto-refresh
          </label>
        </div>

        {/* Terminal Window */}
        <div className="console-container">
          <div className="console-body">
            {logs.map((log, i) => (
              <div key={i} className="log-line">
                <span className="log-time">{log.timestamp}</span>
                <span className={`log-source ${log.source}`}>{log.source.toUpperCase()}</span>
                <span className={`log-level ${log.level.toLowerCase()}`}>{log.level}</span>
                <span className="log-message">{log.message}</span>
                {log.category !== 'General' && (
                  <span className={`log-category ${log.category === 'Tool Execution' ? 'tool' : 'error'}`}>{log.category}</span>
                )}
              </div>
            ))}
            {logs.length === 0 && (
              <div style={{ color: '#555', textAlign: 'center', padding: '40px' }}>No logs found matching filters.</div>
            )}
            <div ref={bottomRef} />
          </div>
        </div>

      </div>
    );
  };

  return (
    <div className="app-container">
      
      {/* Sidebar Navigation */}
      <div className="sidebar">
        <div className="logo-section">
          {/* Creeper Face Icon */}
          <svg width="32" height="32" viewBox="0 0 8 8" fill="var(--color-green)">
            <rect x="0" y="0" width="8" height="8" fill="#156415" />
            <rect x="1" y="2" width="2" height="2" fill="#000000" />
            <rect x="5" y="2" width="2" height="2" fill="#000000" />
            <rect x="3" y="4" width="2" height="2" fill="#000000" />
            <rect x="2" y="5" width="4" height="2" fill="#000000" />
            <rect x="2" y="7" width="1" height="1" fill="#000000" />
            <rect x="5" y="7" width="1" height="1" fill="#000000" />
          </svg>
          <div className="logo-text">
            MINECRAFT AI<br />Companion
          </div>
        </div>

        <div className="nav-menu">
          <div className={`nav-item ${activeTab === 'home' ? 'active' : ''}`} onClick={() => setActiveTab('home')}>
            🏠 Home
          </div>
          <div className={`nav-item ${activeTab === 'config' ? 'active' : ''}`} onClick={() => setActiveTab('config')}>
            ⚙️ AI Config
          </div>
          <div className={`nav-item ${activeTab === 'resources' ? 'active' : ''}`} onClick={() => setActiveTab('resources')}>
            📊 Resource Manager
          </div>
          <div className={`nav-item ${activeTab === 'memory' ? 'active' : ''}`} onClick={() => setActiveTab('memory')}>
            🧠 Memory Manager
          </div>
          <div className={`nav-item ${activeTab === 'tools' ? 'active' : ''}`} onClick={() => setActiveTab('tools')}>
            🛠️ Tool Registry
          </div>
          <div className={`nav-item ${activeTab === 'logs' ? 'active' : ''}`} onClick={() => setActiveTab('logs')}>
            📜 Event Logs
          </div>
        </div>

        <div className="sidebar-footer">
          Platform: v0.4.3<br />
          Core Engine: FastAPI & React
        </div>
      </div>

      {/* Main Content Pane */}
      <div className="main-content">
        
        {/* Page Title & Global Health Banner */}
        <div className="page-header">
          <div>
            <h1 className="page-title">
              {activeTab === 'home' && 'System Dashboard'}
              {activeTab === 'config' && 'Model Configuration'}
              {activeTab === 'resources' && 'AI Resource Telemetry'}
              {activeTab === 'memory' && 'Saved Memory Manager'}
              {activeTab === 'tools' && 'Registered Tools Registry'}
              {activeTab === 'logs' && 'System logs & Diagnostics'}
            </h1>
            <p className="page-subtitle">
              {activeTab === 'home' && 'Live status overview of the Minecraft assistant backend.'}
              {activeTab === 'config' && 'Fine-tune model temperatures, quotas, API keys, and rate limits.'}
              {activeTab === 'resources' && 'Verify input/output token counts, response latency, and hourly usage.'}
              {activeTab === 'memory' && 'Directly inspect and modify locations, notes, and preference indexes.'}
              {activeTab === 'tools' && 'Verify schemas, descriptions, and descriptions of registered tools.'}
              {activeTab === 'logs' && 'Realtime logs aggregated from both launcher and assistant subprocesses.'}
            </p>
          </div>
          
          <div style={{ display: 'flex', gap: '12px' }}>
            <div className={`status-indicator ${backendOnline ? 'active' : 'inactive'}`}>
              Backend: {backendOnline ? 'Online' : 'Offline'}
            </div>
            {stats && (
              <div className={`status-indicator ${stats.launcher_status === 'Active (Connected)' ? 'active' : 'warning'}`}>
                Launcher: {stats.launcher_status === 'Active (Connected)' ? 'Connected' : 'Disconnected'}
              </div>
            )}
          </div>
        </div>

        {/* Selected Tab Render */}
        {activeTab === 'home' && renderHome()}
        {activeTab === 'config' && renderConfig()}
        {activeTab === 'resources' && renderResources()}
        {activeTab === 'memory' && renderMemory()}
        {activeTab === 'tools' && renderTools()}
        {activeTab === 'logs' && renderLogs()}

        {/* Global Toast Notifier */}
        {toast && (
          <div style={{
            position: 'fixed', bottom: '24px', right: '24px', 
            padding: '12px 24px', borderRadius: 'var(--border-radius)',
            backgroundColor: toast.type === 'success' ? '#156415' : '#881515',
            color: '#fff', fontWeight: 'bold', border: `1px solid ${toast.type === 'success' ? '#3cc83c' : '#ff5555'}`,
            boxShadow: '0 4px 15px rgba(0,0,0,0.5)', zIndex: 10000,
            fontSize: '14px', transition: 'all 0.3s'
          }}>
            {toast.type === 'success' ? '✓' : '✗'} {toast.message}
          </div>
        )}

      </div>
    </div>
  );
}
