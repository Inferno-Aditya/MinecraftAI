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
  const [modelsData, setModelsData] = useState(null);
  const [syncLoading, setSyncLoading] = useState(false);
  const [syncWarning, setSyncWarning] = useState('');
  const [toast, setToast] = useState(null);
  const [apiKeysVisible, setApiKeysVisible] = useState(false);
  const [logsAutoRefresh, setLogsAutoRefresh] = useState(true);
  const [diagnostics, setDiagnostics] = useState(null);

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
      fetchModelsData();
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

  // Poll diagnostics when on that tab
  useEffect(() => {
    if (!backendOnline || activeTab !== 'diagnostics') return;
    fetchDiagnostics();
    const interval = setInterval(fetchDiagnostics, 3000);
    return () => clearInterval(interval);
  }, [backendOnline, activeTab]);

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

  const fetchModelsData = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/models`);
      if (res.ok) {
        const data = await res.json();
        setModelsData(data);
        if (data.warning) {
          setSyncWarning(data.warning);
        } else {
          setSyncWarning('');
        }
      }
    } catch (err) {
      console.error('Failed to fetch models data', err);
    }
  };

  const fetchDiagnostics = async () => {
    try {
      const res = await fetch(`${API_BASE}/api/diagnostics`);
      if (res.ok) {
        const data = await res.json();
        setDiagnostics(data);
      }
    } catch (err) {
      console.error('Failed to fetch diagnostics', err);
    }
  };

  const handleSyncModels = async () => {
    setSyncLoading(true);
    try {
      const res = await fetch(`${API_BASE}/api/models/refresh`, {
        method: 'POST'
      });
      if (res.ok) {
        const data = await res.json();
        setModelsData(data);
        if (data.warning) {
          setSyncWarning(data.warning);
          showToast('Model sync completed with warnings.', 'error');
        } else {
          setSyncWarning('');
          showToast('Models synchronized successfully!');
        }
        fetchConfig();
        const statsRes = await fetch(`${API_BASE}/api/resources/stats`);
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData);
        }
      } else {
        showToast('Failed to synchronize models.', 'error');
      }
    } catch (err) {
      showToast('Error synchronizing models.', 'error');
    } finally {
      setSyncLoading(false);
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

  const handleModelChange = async (modelId) => {
    try {
      const res = await fetch(`${API_BASE}/api/models/active`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ model_id: modelId })
      });
      if (res.ok) {
        showToast('Active model switched successfully!');
        fetchConfig();
        fetchModelsData();
        const statsRes = await fetch(`${API_BASE}/api/resources/stats`);
        if (statsRes.ok) {
          const statsData = await statsRes.json();
          setStats(statsData);
        }
      } else {
        const err = await res.json();
        showToast(`Failed to switch model: ${err.detail || 'Error'}`, 'error');
      }
    } catch (err) {
      showToast('Error switching active model.', 'error');
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
      { title: 'Requests Today', value: stats.requests_today, footer: `Session: ${stats.requests_session} | This minute: ${stats.requests_this_minute ?? 0}` },
      { title: 'Remaining Quota (Est.)', value: stats.remaining_quota, footer: 'Estimated from local tracking' },
      { title: 'Token Usage Today', value: stats.total_tokens_today.toLocaleString(), footer: `In: ${stats.input_tokens_today.toLocaleString()} | Out: ${stats.output_tokens_today.toLocaleString()}` },
      { title: 'Average Latency', value: `${stats.average_latency}s`, footer: `Failed: ${stats.failed_requests} | Rate limits: ${stats.rate_limit_events_today ?? 0}` },
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

  const renderPromptProfiler = () => {
    if (!stats) return <div style={{ color: 'var(--color-text-secondary)' }}>Loading telemetry...</div>;

    const latestReq = stats.recent_requests?.[0];
    const profile = latestReq?.prompt_profile || {
      system_prompt_tokens: 0,
      context_tokens: 0,
      memory_tokens: 0,
      tool_tokens: 0,
      user_message_tokens: 0,
      total_prompt_tokens: 0,
      baseline_tokens: 0
    };

    const total = profile.total_prompt_tokens || 1;
    const pctSystem = (profile.system_prompt_tokens / total) * 100;
    const pctContext = (profile.context_tokens / total) * 100;
    const pctMemory = (profile.memory_tokens / total) * 100;
    const pctTools = (profile.tool_tokens / total) * 100;
    const pctUser = (profile.user_message_tokens / total) * 100;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        {/* Metrics Row */}
        <div className="stats-grid">
          <div className="card">
            <div className="card-title">Avg Prompt Size</div>
            <div className="card-value">{stats.average_prompt_size}</div>
            <div className="card-footer">Actual tokens sent</div>
          </div>
          <div className="card">
            <div className="card-title">Avg Response Size</div>
            <div className="card-value">{stats.average_response_size}</div>
            <div className="card-footer">Generation length</div>
          </div>
          <div className="card">
            <div className="card-title">Avg Tokens Saved</div>
            <div className="card-value" style={{ color: 'var(--color-green)' }}>
              {stats.average_tokens_saved}
            </div>
            <div className="card-footer">Per request savings</div>
          </div>
          <div className="card">
            <div className="card-title">Token Reduction</div>
            <div className="card-value" style={{ color: 'var(--color-green)' }}>
              {stats.percentage_reduction}%
            </div>
            <div className="card-footer">Average size reduction</div>
          </div>
          <div className="card">
            <div className="card-title">Latency Improvement</div>
            <div className="card-value" style={{ color: 'var(--color-info)' }}>
              ~{stats.estimated_latency_improvement}s
            </div>
            <div className="card-footer">Estimated time saved</div>
          </div>
        </div>

        {/* Breakdown and Largest Row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
          {/* Visual Breakdown Card */}
          <div className="form-section">
            <div className="form-title">Latest Request Breakdown ({latestReq?.model || 'No request yet'})</div>
            {latestReq ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                {/* Stacked bar */}
                <div style={{
                  display: 'flex', height: '24px', borderRadius: '4px', overflow: 'hidden', 
                  backgroundColor: '#222', width: '100%', border: '1px solid #333'
                }}>
                  <div style={{ width: `${pctSystem}%`, backgroundColor: '#ffaa00', height: '100%' }} title={`System: ${profile.system_prompt_tokens} tokens`} />
                  <div style={{ width: `${pctContext}%`, backgroundColor: '#3cc83c', height: '100%' }} title={`Context: ${profile.context_tokens} tokens`} />
                  <div style={{ width: `${pctMemory}%`, backgroundColor: '#5555ff', height: '100%' }} title={`Memory: ${profile.memory_tokens} tokens`} />
                  <div style={{ width: `${pctTools}%`, backgroundColor: '#ff5555', height: '100%' }} title={`Tools: ${profile.tool_tokens} tokens`} />
                  <div style={{ width: `${pctUser}%`, backgroundColor: '#aaaaaa', height: '100%' }} title={`User Message: ${profile.user_message_tokens} tokens`} />
                </div>

                {/* Legend with tokens and labels */}
                <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', fontSize: '14px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '12px', height: '12px', borderRadius: '2px', backgroundColor: '#ffaa00' }} />
                      <span>System Prompt</span>
                    </div>
                    <span style={{ fontFamily: 'monospace' }}>{profile.system_prompt_tokens} tokens</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '12px', height: '12px', borderRadius: '2px', backgroundColor: '#3cc83c' }} />
                      <span>Player Context</span>
                    </div>
                    <span style={{ fontFamily: 'monospace' }}>{profile.context_tokens} tokens</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '12px', height: '12px', borderRadius: '2px', backgroundColor: '#5555ff' }} />
                      <span>Memory Summary</span>
                    </div>
                    <span style={{ fontFamily: 'monospace' }}>{profile.memory_tokens} tokens</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '12px', height: '12px', borderRadius: '2px', backgroundColor: '#ff5555' }} />
                      <span>Tool Definitions</span>
                    </div>
                    <span style={{ fontFamily: 'monospace' }}>{profile.tool_tokens} tokens</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div style={{ width: '12px', height: '12px', borderRadius: '2px', backgroundColor: '#aaaaaa' }} />
                      <span>User Message</span>
                    </div>
                    <span style={{ fontFamily: 'monospace' }}>{profile.user_message_tokens} tokens</span>
                  </div>
                  <div style={{ borderTop: '1px solid #222', paddingTop: '10px', display: 'flex', justifyContent: 'space-between', fontWeight: 'bold' }}>
                    <span>Total Prompt Size</span>
                    <span style={{ color: 'var(--color-green)' }}>{profile.total_prompt_tokens} / {profile.baseline_tokens} baseline</span>
                  </div>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px', color: 'var(--color-green)' }}>
                    <span>Optimization Savings</span>
                    <span>-{profile.baseline_tokens - profile.total_prompt_tokens} tokens saved ({((profile.baseline_tokens - profile.total_prompt_tokens) / (profile.baseline_tokens || 1) * 100).toFixed(1)}% reduction)</span>
                  </div>
                </div>
              </div>
            ) : (
              <div style={{ color: 'var(--color-text-secondary)' }}>No request data available.</div>
            )}
          </div>

          {/* Largest Prompts Card */}
          <div className="form-section">
            <div className="form-title">Largest Prompts (Top 5)</div>
            <table style={{ width: '100%', borderCollapse: 'collapse' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #222', textAlign: 'left', color: 'var(--color-text-secondary)', fontSize: '13px' }}>
                  <th style={{ padding: '8px 12px' }}>Timestamp</th>
                  <th style={{ padding: '8px 12px' }}>Actual Size</th>
                  <th style={{ padding: '8px 12px' }}>Baseline</th>
                  <th style={{ padding: '8px 12px' }}>Saved</th>
                </tr>
              </thead>
              <tbody>
                {stats.largest_prompts?.map((r, i) => (
                  <tr key={i} style={{ borderBottom: '1px solid #1a1a1a', fontSize: '14px' }}>
                    <td style={{ padding: '8px 12px', color: '#888' }}>{new Date(r.timestamp).toLocaleTimeString()}</td>
                    <td style={{ padding: '8px 12px', fontWeight: '600' }}>{r.total_prompt_tokens}</td>
                    <td style={{ padding: '8px 12px', color: '#ccc' }}>{r.baseline_tokens}</td>
                    <td style={{ padding: '8px 12px', color: 'var(--color-green)' }}>-{r.tokens_saved}</td>
                  </tr>
                ))}
                {(!stats.largest_prompts || stats.largest_prompts.length === 0) && (
                  <tr>
                    <td colSpan="4" style={{ padding: '20px', textAlign: 'center', color: '#666' }}>No requests recorded yet.</td>
                  </tr>
                )}
              </tbody>
            </table>
          </div>
        </div>

        {/* History table */}
        <div className="form-section">
          <div className="form-title">Prompt History Breakdown</div>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid #222', textAlign: 'left', color: 'var(--color-text-secondary)', fontSize: '13px' }}>
                <th style={{ padding: '12px' }}>Timestamp</th>
                <th style={{ padding: '12px' }}>Model</th>
                <th style={{ padding: '12px' }}>Actual (Baseline)</th>
                <th style={{ padding: '12px' }}>Breakdown (Sys/Ctx/Mem/Tool/User)</th>
                <th style={{ padding: '12px' }}>Savings</th>
              </tr>
            </thead>
            <tbody>
              {stats.recent_requests.map((r, i) => {
                const p = r.prompt_profile || {
                  system_prompt_tokens: r.input_tokens,
                  context_tokens: 0,
                  memory_tokens: 0,
                  tool_tokens: 0,
                  user_message_tokens: 0,
                  total_prompt_tokens: r.input_tokens,
                  baseline_tokens: r.input_tokens
                };
                return (
                  <tr key={i} style={{ borderBottom: '1px solid #1a1a1a', fontSize: '14px' }}>
                    <td style={{ padding: '12px', color: '#888' }}>{new Date(r.timestamp).toLocaleTimeString()}</td>
                    <td style={{ padding: '12px', color: '#ccc' }}>{r.model}</td>
                    <td style={{ padding: '12px', fontWeight: '500' }}>
                      {p.total_prompt_tokens} <span style={{ fontSize: '12px', color: '#666' }}>({p.baseline_tokens})</span>
                    </td>
                    <td style={{ padding: '12px', fontFamily: 'monospace' }}>
                      <span style={{ color: '#ffaa00' }}>{p.system_prompt_tokens}</span>/
                      <span style={{ color: '#3cc83c' }}>{p.context_tokens}</span>/
                      <span style={{ color: '#5555ff' }}>{p.memory_tokens}</span>/
                      <span style={{ color: '#ff5555' }}>{p.tool_tokens}</span>/
                      <span style={{ color: '#aaaaaa' }}>{p.user_message_tokens}</span>
                    </td>
                    <td style={{ padding: '12px', color: p.baseline_tokens - p.total_prompt_tokens > 0 ? 'var(--color-green)' : '#ccc' }}>
                      {p.baseline_tokens - p.total_prompt_tokens > 0 ? `-${p.baseline_tokens - p.total_prompt_tokens} (${((p.baseline_tokens - p.total_prompt_tokens)/p.baseline_tokens * 100).toFixed(0)}%)` : '0%'}
                    </td>
                  </tr>
                );
              })}
              {stats.recent_requests.length === 0 && (
                <tr>
                  <td colSpan="5" style={{ padding: '20px', textAlign: 'center', color: '#666' }}>No requests recorded yet.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  const renderModelManager = () => {
    // Determine the source of model definitions (prefer rich modelsData from GET /api/models)
    const mData = modelsData || {
      active_model: stats?.current_model || 'gemini-2.5-flash',
      active_provider: stats?.current_provider || 'gemini',
      supported_models: stats?.model_benchmarks || {}
    };

    const activeId = mData.active_model;
    const activeModel = mData.supported_models[activeId] || {
      name: activeId,
      provider: mData.active_provider,
      description: 'Active model profile',
      rpm: 15,
      rpd: 1500,
      context_window: 1000000,
      output_token_limit: 8192,
      recommended_usage: 'General'
    };

    const geminiAvail = providers.find(p => p.id === 'gemini')?.available ?? false;

    // Only show selectable (non-hidden, supports_chat) models in the dropdown and table
    const selectableModels = Object.fromEntries(
      Object.entries(mData.supported_models || {}).filter(
        ([, m]) => !m.is_hidden && m.supports_chat
      )
    );

    // All models (including hidden) for the registry diagnostic section
    const allModels = mData.supported_models || {};
    const hiddenCount = Object.values(allModels).filter(m => m.is_hidden).length;

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        
        {/* Sync Fallback / Active Removed Warning Alert */}
        {syncWarning && (
          <div style={{
            padding: '16px',
            borderRadius: 'var(--border-radius)',
            border: '1px solid #ff5555',
            backgroundColor: '#331111',
            color: '#ffaaaa',
            fontSize: '14px',
            lineHeight: '1.5'
          }}>
            ⚠️ <strong>Sync Warning:</strong> {syncWarning}
          </div>
        )}

        {/* Model Selection and Active Profile Row */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 2fr', gap: '20px' }}>
          
          {/* Selector Card */}
          <div className="form-section" style={{ height: 'fit-content' }}>
            <div className="form-title">Active AI Model</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                <label style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>Select Active Model</label>
                <select 
                  value={activeId}
                  onChange={(e) => handleModelChange(e.target.value)}
                  style={{
                    padding: '10px 14px',
                    borderRadius: 'var(--border-radius)',
                    backgroundColor: '#1a1a1a',
                    border: '1px solid #333',
                    color: '#fff',
                    fontSize: '14px',
                    cursor: 'pointer',
                    width: '100%'
                  }}
                >
                  {Object.keys(selectableModels).map((mId) => (
                    <option key={mId} value={mId}>
                      {selectableModels[mId].icon || '🤖'} {selectableModels[mId].name}
                    </option>
                  ))}
                </select>
              </div>

              <div style={{ 
                padding: '12px', 
                borderRadius: 'var(--border-radius)', 
                backgroundColor: 'rgba(60, 200, 60, 0.05)', 
                border: '1px solid rgba(60, 200, 60, 0.2)',
                fontSize: '13px',
                lineHeight: '1.4'
              }}>
                🌟 Gemma 4 is configured as the platform default model and will be selected automatically for new installations.
              </div>
            </div>
          </div>

          {/* Active Model Details Card */}
          <div className="form-section">
            <div className="form-title" style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <span>Active Model Profile</span>
              <span style={{ 
                fontSize: '11px', 
                fontWeight: 'bold', 
                backgroundColor: activeModel.provider === 'mock' ? '#555' : 'var(--color-info)',
                padding: '4px 8px', 
                borderRadius: '4px',
                color: '#fff',
                textTransform: 'uppercase'
              }}>
                {activeModel.provider}
              </span>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                <span style={{ fontSize: '24px' }}>{activeModel.icon || '🤖'}</span>
                <span style={{ fontSize: '18px', fontWeight: 'bold', color: 'var(--color-green)' }}>{activeModel.name}</span>
                {activeModel.badge && (
                  <span style={{ 
                    fontSize: '11px', 
                    padding: '2px 6px', 
                    borderRadius: '4px', 
                    backgroundColor: 'var(--color-green)', 
                    color: '#fff',
                    fontWeight: 'bold'
                  }}>
                    {activeModel.badge}
                  </span>
                )}
              </div>

              <p style={{ fontSize: '14px', color: '#ccc', margin: 0, lineHeight: 1.5 }}>
                {activeModel.description}
              </p>

              <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '16px', fontSize: '13px', borderTop: '1px solid #222', paddingTop: '14px' }}>
                <div>
                  <strong style={{ color: 'var(--color-text-secondary)' }}>Recommended Usage:</strong>
                  <p style={{ margin: '4px 0 0 0', color: '#aaa' }}>{activeModel.recommended_usage || 'No recommendations set'}</p>
                </div>
                <div>
                  <strong style={{ color: 'var(--color-text-secondary)' }}>Context Window:</strong>
                  <p style={{ margin: '4px 0 0 0', color: '#aaa', fontFamily: 'monospace' }}>
                    {activeModel.context_window?.toLocaleString() || 'N/A'} tokens
                  </p>
                </div>
                <div>
                  <strong style={{ color: 'var(--color-text-secondary)' }}>Max Output Limit:</strong>
                  <p style={{ margin: '4px 0 0 0', color: '#aaa', fontFamily: 'monospace' }}>
                    {activeModel.output_token_limit?.toLocaleString() || 'N/A'} tokens
                  </p>
                </div>
                <div>
                  <strong style={{ color: 'var(--color-text-secondary)' }}>Rate Limits:</strong>
                  <p style={{ margin: '4px 0 0 0', color: '#aaa' }}>
                    {activeModel.rpm} RPM / {activeModel.rpd?.toLocaleString() || 'N/A'} RPD
                  </p>
                </div>
              </div>
            </div>
          </div>
        </div>

        {/* Discovered Models Registry Section */}
        <div className="form-section">
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
            <div>
              <div className="form-title" style={{ border: 'none', padding: '0', margin: '0' }}>Discovered Models Registry</div>
              {hiddenCount > 0 && (
                <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px' }}>
                  {hiddenCount} non-chat model{hiddenCount !== 1 ? 's' : ''} hidden (TTS, image, music, research) — visible in /api/diagnostics
                </div>
              )}
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <span style={{ fontSize: '13px', color: 'var(--color-text-secondary)' }}>
                Last Synced: {modelsData?.last_sync_time ? new Date(modelsData.last_sync_time).toLocaleString() : 'Never (Bootstrapped)'}
              </span>
              <button className="btn" onClick={handleSyncModels} disabled={syncLoading} style={{ minWidth: '120px' }}>
                {syncLoading ? 'Syncing...' : 'Sync Models'}
              </button>
            </div>
          </div>

          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '700px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #222', textAlign: 'left', color: 'var(--color-text-secondary)', fontSize: '13px' }}>
                  <th style={{ padding: '12px' }}>Model Details</th>
                  <th style={{ padding: '12px' }}>Provider</th>
                  <th style={{ padding: '12px' }}>Source</th>
                  <th style={{ padding: '12px' }}>Capabilities</th>
                  <th style={{ padding: '12px' }}>Context Window</th>
                  <th style={{ padding: '12px' }}>Action</th>
                </tr>
              </thead>
              <tbody>
                {Object.keys(selectableModels).map((mId) => {
                  const m = selectableModels[mId];
                  const isActive = mId === activeId;
                  
                  // Status
                  let statusText = m.discovery_source || 'Available';
                  let statusColor = 'var(--color-text-secondary)';
                  if (m.discovery_source === 'api') { statusText = 'Live API'; statusColor = 'var(--color-green)'; }
                  else if (m.discovery_source === 'cache') { statusText = 'Cached'; statusColor = '#ffaa00'; }
                  else if (m.discovery_source === 'hardcoded') { statusText = 'Default'; statusColor = '#888'; }

                  if (m.provider === 'gemini' && !geminiAvail) {
                    statusText = 'Key Required';
                    statusColor = '#ff5555';
                  }

                  return (
                    <tr key={mId} style={{ 
                      borderBottom: '1px solid #1a1a1a', 
                      fontSize: '14px',
                      backgroundColor: isActive ? 'rgba(60, 200, 60, 0.02)' : 'transparent'
                    }}>
                      <td style={{ padding: '12px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '8px', fontWeight: '600' }}>
                          <span>{m.icon || '🤖'}</span>
                          <span style={{ color: isActive ? 'var(--color-green)' : '#fff' }}>{m.name}</span>
                          {m.badge && (
                            <span style={{ 
                              fontSize: '10px', 
                              padding: '2px 6px', 
                              borderRadius: '4px', 
                              backgroundColor: m.badge === 'Default' ? 'var(--color-green)' : '#555', 
                              color: '#fff',
                              fontWeight: 'bold'
                            }}>
                              {m.badge}
                            </span>
                          )}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)', marginTop: '4px', maxWidth: '300px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={m.description}>
                          {m.description}
                        </div>
                      </td>
                      <td style={{ padding: '12px', textTransform: 'uppercase', fontSize: '12px', color: '#ccc' }}>
                        {m.provider}
                      </td>
                      <td style={{ padding: '12px', color: statusColor, fontWeight: '500' }}>
                        {statusText}
                      </td>
                      <td style={{ padding: '12px' }}>
                        <div style={{ display: 'flex', gap: '6px', flexWrap: 'wrap' }}>
                          {m.supports_chat && (
                            <span style={{ fontSize: '11px', backgroundColor: 'rgba(60,200,60,0.1)', border: '1px solid rgba(60,200,60,0.3)', padding: '2px 6px', borderRadius: '4px', color: 'var(--color-green)' }}>
                              Chat
                            </span>
                          )}
                          {m.supports_tools && (
                            <span style={{ fontSize: '11px', backgroundColor: '#222', border: '1px solid #333', padding: '2px 6px', borderRadius: '4px' }}>
                              Tools
                            </span>
                          )}
                          {m.supports_json_mode && (
                            <span style={{ fontSize: '11px', backgroundColor: 'rgba(0,120,200,0.1)', border: '1px solid rgba(0,120,200,0.3)', padding: '2px 6px', borderRadius: '4px', color: '#7cc' }}>
                              JSON
                            </span>
                          )}
                        </div>
                      </td>
                      <td style={{ padding: '12px', fontFamily: 'monospace', color: '#ccc' }}>
                        {m.context_window?.toLocaleString() || 'N/A'}
                      </td>
                      <td style={{ padding: '12px' }}>
                        {isActive ? (
                          <span style={{ color: 'var(--color-green)', fontWeight: 'bold' }}>Active</span>
                        ) : (
                          <button 
                            className="btn" 
                            onClick={() => handleModelChange(mId)} 
                            style={{ 
                              padding: '6px 12px', 
                              fontSize: '12px',
                              backgroundColor: '#222',
                              border: '1px solid #444'
                            }}
                          >
                            Select
                          </button>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      </div>
    );
  };

  const renderModelBenchmarks = () => {
    if (!stats || !stats.model_benchmarks) {
      return <div style={{ color: 'var(--color-text-secondary)' }}>Loading benchmarking data...</div>;
    }

    const models = Object.keys(stats.model_benchmarks).map(mId => ({
      id: mId,
      ...stats.model_benchmarks[mId]
    }));

    // Find max average latency to scale the latency bar chart
    const maxLatency = Math.max(...models.map(m => m.average_latency), 1.0);

    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
        
        {/* Visual Latency Benchmark Chart */}
        <div className="form-section">
          <div className="form-title">Average Latency Comparison (seconds)</div>
          <div style={{ display: 'flex', flexDirection: 'column', gap: '14px', padding: '10px 0' }}>
            {models.map((m) => {
              const pct = (m.average_latency / maxLatency) * 100;
              const hasData = m.requests > 0;
              return (
                <div key={m.id} style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                  <div style={{ width: '180px', fontSize: '14px', fontWeight: '500', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }} title={m.name}>
                    {m.name}
                  </div>
                  <div style={{ flex: 1, height: '20px', backgroundColor: '#111', borderRadius: '4px', overflow: 'hidden', position: 'relative' }}>
                    {hasData ? (
                      <div style={{
                        width: `${pct}%`,
                        height: '100%',
                        backgroundColor: m.id === stats.current_model ? 'var(--color-green)' : 'var(--color-info)',
                        borderRadius: '4px',
                        transition: 'width 0.5s ease-in-out'
                      }} />
                    ) : (
                      <span style={{ position: 'absolute', left: '10px', top: '2px', fontSize: '11px', color: '#555' }}>No telemetry data</span>
                    )}
                  </div>
                  <div style={{ width: '80px', fontSize: '14px', fontFamily: 'monospace', textAlign: 'right', fontWeight: 'bold' }}>
                    {hasData ? `${m.average_latency.toFixed(2)}s` : 'N/A'}
                  </div>
                </div>
              );
            })}
          </div>
        </div>

        {/* Benchmarking Comparison Table */}
        <div className="form-section">
          <div className="form-title">Model Performance & Reliability Matrix</div>
          <div style={{ overflowX: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', minWidth: '800px' }}>
              <thead>
                <tr style={{ borderBottom: '2px solid #222', textAlign: 'left', color: 'var(--color-text-secondary)', fontSize: '13px' }}>
                  <th style={{ padding: '12px' }}>Model</th>
                  <th style={{ padding: '12px' }}>Requests</th>
                  <th style={{ padding: '12px' }}>Avg Prompt / Response</th>
                  <th style={{ padding: '12px' }}>Success Rate</th>
                  <th style={{ padding: '12px' }}>Tool Success Rate</th>
                  <th style={{ padding: '12px' }}>Rate Limit Events</th>
                  <th style={{ padding: '12px' }}>Errors</th>
                </tr>
              </thead>
              <tbody>
                {models.map((m) => {
                  const hasData = m.requests > 0;
                  return (
                    <tr key={m.id} style={{ 
                      borderBottom: '1px solid #1a1a1a', 
                      fontSize: '14px',
                      backgroundColor: m.id === stats.current_model ? 'rgba(60, 200, 60, 0.03)' : 'transparent'
                    }}>
                      <td style={{ padding: '12px' }}>
                        <div style={{ fontWeight: '600', color: m.id === stats.current_model ? 'var(--color-green)' : '#fff' }}>
                          {m.name} {m.id === stats.current_model && '★'}
                        </div>
                        <div style={{ fontSize: '12px', color: 'var(--color-text-secondary)' }}>{m.provider} provider</div>
                      </td>
                      <td style={{ padding: '12px', fontFamily: 'monospace' }}>{m.requests}</td>
                      <td style={{ padding: '12px', fontFamily: 'monospace' }}>
                        {hasData ? `${m.average_prompt_tokens.toFixed(0)} / ${m.average_response_tokens.toFixed(0)}` : 'N/A'}
                      </td>
                      <td style={{ padding: '12px', color: hasData ? (m.success_rate >= 90 ? 'var(--color-green)' : '#ffaa00') : '#ccc' }}>
                        {hasData ? `${m.success_rate}%` : 'N/A'}
                      </td>
                      <td style={{ padding: '12px', color: m.tool_calls_attempted > 0 ? (m.tool_success_rate >= 90 ? 'var(--color-green)' : '#ffaa00') : '#ccc' }}>
                        {m.tool_calls_attempted > 0 ? `${m.tool_success_rate}%` : 'N/A'}
                      </td>
                      <td style={{ padding: '12px', fontFamily: 'monospace', color: m.rate_limit_events > 0 ? '#ff5555' : '#ccc' }}>
                        {m.rate_limit_events}
                      </td>
                      <td style={{ padding: '12px', fontSize: '13px' }}>
                        {m.recent_errors && m.recent_errors.length > 0 ? (
                          <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', color: '#ff5555' }}>
                            {m.recent_errors.slice(-2).map((err, idx) => (
                              <div key={idx} style={{ overflow: 'hidden', textOverflow: 'ellipsis', maxWidth: '200px', whiteSpace: 'nowrap' }} title={err}>
                                • {err}
                              </div>
                            ))}
                          </div>
                        ) : (
                          <span style={{ color: 'var(--color-text-secondary)' }}>None</span>
                        )}
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
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

  const renderDiagnostics = () => {
    if (!diagnostics) {
      return (
        <div style={{ padding: '40px', textAlign: 'center', color: '#888' }}>
          Loading developer diagnostics data from backend...
        </div>
      );
    }

    const {
      active_provider,
      active_model,
      model_capabilities,
      discovery_source,
      last_sync_time,
      last_request_id,
      last_request_message,
      last_request_strategy,
      last_request_tools,
      last_response_status,
      last_response_time_ms,
      last_input_tokens,
      last_output_tokens,
      last_exception,
      last_exception_type,
      failure_category,
      current_state,
      last_successful_request_id,
      last_provider_payload,
      stage_timings,
      last_executed_tool,
      tool_execution_time_ms,
      tool_status,
      tool_output,
      tool_exception,
    } = diagnostics;

    // ── Request Timeline helpers ─────────────────────────────────────────
    const CATEGORY_COLORS = {
      NETWORK_TIMEOUT: '#ff8c42',
      PROVIDER_TIMEOUT: '#ff5f5f',
      CONNECTION_FAILURE: '#c0392b',
      RATE_LIMIT: '#f1c40f',
      DAILY_QUOTA_EXCEEDED: '#e67e22',
      JSON_PARSE_ERROR: '#9b59b6',
      INVALID_PROVIDER_RESPONSE: '#8e44ad',
      GENERATOR_TIMEOUT: '#e74c3c',
      PLANNER_TIMEOUT: '#e74c3c',
      TOOL_EXECUTION_ERROR: '#d35400',
      REQUEST_BUDGET_EXCEEDED: '#c0392b',
      UNKNOWN_PROVIDER_EXCEPTION: '#95a5a6',
      NONE: 'var(--color-green)',
    };

    const getCategoryColor = (cat) => CATEGORY_COLORS[cat] || '#95a5a6';

    const renderTimeline = () => {
      if (!last_request_id || !stage_timings || stage_timings.length === 0) return null;
      const total = stage_timings.reduce((s, t) => s + t.elapsed_ms, 0) || 1;
      return (
        <div className="card">
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
            <h3 className="card-title" style={{ margin: 0 }}>⏱ Request Timeline</h3>
            <span style={{
              fontSize: '11px', fontFamily: 'monospace', color: '#666',
              background: '#111', border: '1px solid #222', padding: '2px 8px', borderRadius: '4px'
            }}>
              REQ:{last_request_id}
            </span>
          </div>
          <p style={{ fontSize: '12px', color: '#555', margin: '4px 0 20px', fontStyle: 'italic' }}>
            End-to-end breakdown of every pipeline stage for this request.
          </p>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            {stage_timings.map((stage, idx) => {
              const pct = Math.max(2, (stage.elapsed_ms / total) * 100);
              const ok = stage.success !== false && !stage.error;
              const barColor = ok ? 'var(--color-green)' : getCategoryColor(stage.failure_category);
              return (
                <div key={idx} style={{ display: 'flex', flexDirection: 'column', gap: '3px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', fontSize: '13px' }}>
                    <span style={{ fontFamily: 'monospace', display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <span style={{ color: ok ? 'var(--color-green)' : '#ff5555', fontWeight: 'bold', fontSize: '15px' }}>
                        {ok ? '✓' : '✗'}
                      </span>
                      <span style={{ color: '#ccc' }}>{stage.stage}</span>
                    </span>
                    <span style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      {stage.failure_category && stage.failure_category !== 'NONE' && !ok && (
                        <span style={{
                          fontSize: '10px', padding: '2px 6px', borderRadius: '4px',
                          backgroundColor: getCategoryColor(stage.failure_category) + '22',
                          border: `1px solid ${getCategoryColor(stage.failure_category)}`,
                          color: getCategoryColor(stage.failure_category),
                          fontFamily: 'monospace',
                        }}>
                          {stage.failure_category}
                        </span>
                      )}
                      <span style={{ color: ok ? '#888' : '#ff8888', fontFamily: 'monospace' }}>
                        {stage.elapsed_ms} ms
                      </span>
                    </span>
                  </div>
                  <div style={{ height: '6px', backgroundColor: '#1a1a1a', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{
                      height: '100%',
                      width: `${pct}%`,
                      backgroundColor: barColor,
                      borderRadius: '3px',
                      transition: 'width 0.4s ease',
                      opacity: ok ? 1 : 0.75,
                    }} />
                  </div>
                  {stage.error && (
                    <span style={{ fontSize: '11px', color: '#ff8888', fontFamily: 'monospace', paddingLeft: '22px' }}>
                      ↳ {stage.error.slice(0, 120)}{stage.error.length > 120 ? '…' : ''}
                    </span>
                  )}
                </div>
              );
            })}
          </div>

          {/* Total row */}
          <div style={{
            marginTop: '16px', paddingTop: '12px', borderTop: '1px solid #222',
            display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          }}>
            <span style={{ fontFamily: 'monospace', fontSize: '13px', color: '#888' }}>
              • TOTAL
            </span>
            <span style={{ fontFamily: 'monospace', fontSize: '14px', fontWeight: 'bold', color: 'var(--color-green)' }}>
              {last_response_time_ms} ms
            </span>
          </div>
        </div>
      );
    };


    return (
      <div style={{ display: 'flex', flexDirection: 'column', gap: '24px', paddingBottom: '40px' }}>
        
        {/* Row 1: Model & Provider Metadata */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '20px' }}>
          <div className="card">
            <h3 className="card-title">🔬 Active Model Metadata</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '16px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #222', paddingBottom: '8px' }}>
                <span style={{ color: '#888' }}>Active Provider:</span>
                <span style={{ fontWeight: 'bold', color: 'var(--color-green)' }}>{active_provider?.toUpperCase()}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #222', paddingBottom: '8px' }}>
                <span style={{ color: '#888' }}>Active Model:</span>
                <span style={{ fontWeight: 'bold' }}>{active_model}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #222', paddingBottom: '8px' }}>
                <span style={{ color: '#888' }}>Discovery Source:</span>
                <span style={{ textTransform: 'capitalize' }}>{discovery_source}</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#888' }}>Last Registry Sync:</span>
                <span>{last_sync_time}</span>
              </div>
            </div>
          </div>

          <div className="card">
            <h3 className="card-title">⚡ Capabilities & Limits</h3>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: '8px', marginTop: '16px' }}>
              <span className={`badge ${model_capabilities?.supports_chat ? 'success' : 'danger'}`}>
                {model_capabilities?.supports_chat ? '✓ Supports Chat' : '✗ No Chat'}
              </span>
              <span className={`badge ${model_capabilities?.supports_tools ? 'success' : 'danger'}`}>
                {model_capabilities?.supports_tools ? '✓ Supports Tools' : '✗ No Tools'}
              </span>
              <span className={`badge ${model_capabilities?.supports_json_mode ? 'success' : 'danger'}`}>
                {model_capabilities?.supports_json_mode ? '✓ Supports JSON Mode' : '✗ No JSON'}
              </span>
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px', marginTop: '20px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', borderBottom: '1px solid #222', paddingBottom: '8px' }}>
                <span style={{ color: '#888' }}>Context Window:</span>
                <span>{model_capabilities?.context_window?.toLocaleString()} tokens</span>
              </div>
              <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                <span style={{ color: '#888' }}>Output Token Limit:</span>
                <span>{model_capabilities?.output_token_limit?.toLocaleString()} tokens</span>
              </div>
            </div>
          </div>
        </div>

        {/* Row 2: Request Telemetry Summary */}
        <div className="card">
          <h3 className="card-title">📡 Latest Request Tracing</h3>
          {!last_request_id ? (
            <p style={{ color: '#666', marginTop: '16px', fontStyle: 'italic' }}>No chat requests traced in this session yet.</p>
          ) : (
            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '16px', marginTop: '16px' }}>
              <div style={{ backgroundColor: '#111', padding: '12px', borderRadius: '6px', border: '1px solid #222' }}>
                <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>Request ID</div>
                <div style={{ fontWeight: 'bold', fontFamily: 'monospace', fontSize: '15px' }}>{last_request_id}</div>
              </div>
              <div style={{ backgroundColor: '#111', padding: '12px', borderRadius: '6px', border: '1px solid #222' }}>
                <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>Latency / Response Time</div>
                <div style={{ fontWeight: 'bold', fontSize: '16px', color: 'var(--color-green)' }}>{last_response_time_ms} ms</div>
              </div>
              <div style={{ backgroundColor: '#111', padding: '12px', borderRadius: '6px', border: '1px solid #222' }}>
                <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>Chosen Strategy</div>
                <div style={{ fontWeight: 'bold', fontSize: '15px' }}>{last_request_strategy || 'None'}</div>
              </div>
              <div style={{ backgroundColor: '#111', padding: '12px', borderRadius: '6px', border: '1px solid #222' }}>
                <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>Status</div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <span className={`badge ${last_response_status === 'success' ? 'success' : 'danger'}`} style={{ fontSize: '12px', padding: '4px 8px' }}>
                    {last_response_status.toUpperCase()}
                  </span>
                  {current_state && (
                    <span style={{
                      fontSize: '10px', fontFamily: 'monospace', padding: '2px 6px',
                      borderRadius: '3px', width: 'fit-content',
                      backgroundColor: current_state === 'COMPLETED' ? '#0a1f0a' : current_state === 'FAILED' ? '#1f0a0a' : '#0d1117',
                      border: `1px solid ${current_state === 'COMPLETED' ? 'var(--color-green)' : current_state === 'FAILED' ? '#ff5555' : '#444'}`,
                      color: current_state === 'COMPLETED' ? 'var(--color-green)' : current_state === 'FAILED' ? '#ff5555' : '#888',
                    }}>
                      {current_state}
                    </span>
                  )}
                </div>
              </div>
              <div style={{ backgroundColor: '#111', padding: '12px', borderRadius: '6px', border: '1px solid #222' }}>
                <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>Tokens (In / Out)</div>
                <div style={{ fontWeight: 'bold' }}>{last_input_tokens} / {last_output_tokens}</div>
              </div>
            </div>
          )}

          {last_request_id && (
            <div style={{ marginTop: '16px', backgroundColor: '#111', padding: '12px', borderRadius: '6px', border: '1px solid #222' }}>
              <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>User Prompt</div>
              <div style={{ fontStyle: 'italic', color: '#ccc' }}>"{last_request_message}"</div>
            </div>
          )}
        </div>

        {/* Row 2b: Request Lifecycle State Tracker */}
        {last_request_id && (
          <div className="card">
            <h3 className="card-title">🔄 Request Lifecycle State</h3>
            <p style={{ fontSize: '12px', color: '#555', margin: '4px 0 20px', fontStyle: 'italic' }}>
              Shows the last recorded lifecycle state for this request.
            </p>
            {(() => {
              const STATES = ['QUEUED', 'PLANNING', 'EXECUTING_TOOLS', 'GENERATING_RESPONSE', 'SENDING_RESPONSE', 'COMPLETED'];
              const isFailed = current_state === 'FAILED';
              const activeIdx = isFailed ? -1 : STATES.indexOf(current_state);
              return (
                <div style={{ display: 'flex', alignItems: 'center', gap: '0', flexWrap: 'wrap', rowGap: '12px' }}>
                  {STATES.map((state, idx) => {
                    const isDone = !isFailed && idx < activeIdx;
                    const isActive = !isFailed && idx === activeIdx;
                    return (
                      <div key={state} style={{ display: 'flex', alignItems: 'center' }}>
                        <div style={{
                          padding: '6px 14px',
                          borderRadius: '20px',
                          fontSize: '11px',
                          fontFamily: 'monospace',
                          fontWeight: isActive ? 'bold' : 'normal',
                          border: `1px solid ${
                            isActive ? 'var(--color-green)'
                            : isDone ? '#2a4a2a'
                            : '#2a2a2a'
                          }`,
                          backgroundColor: isActive ? '#0a2a0a' : isDone ? '#111a11' : '#0d0d0d',
                          color: isActive ? 'var(--color-green)' : isDone ? '#3a7a3a' : '#444',
                          boxShadow: isActive ? '0 0 8px rgba(0,200,100,0.2)' : 'none',
                          transition: 'all 0.3s ease',
                          whiteSpace: 'nowrap',
                        }}>
                          {isDone ? '✓ ' : isActive ? '▶ ' : ''}{state}
                        </div>
                        {idx < STATES.length - 1 && (
                          <div style={{
                            width: '24px', height: '1px',
                            backgroundColor: isDone ? '#2a4a2a' : '#222',
                            margin: '0 2px',
                          }} />
                        )}
                      </div>
                    );
                  })}
                  {isFailed && (
                    <>
                      <div style={{
                        padding: '6px 14px', borderRadius: '20px',
                        fontSize: '11px', fontFamily: 'monospace', fontWeight: 'bold',
                        border: '1px solid #c0392b', backgroundColor: '#1a0808',
                        color: '#ff5555', boxShadow: '0 0 8px rgba(200,0,0,0.2)',
                        whiteSpace: 'nowrap',
                      }}>
                        ✗ FAILED
                      </div>
                    </>
                  )}
                </div>
              );
            })()}
          </div>
        )}

        <div className="card">
          <h3 className="card-title">🛠️ Tool Execution Audit</h3>
          {!last_executed_tool ? (
            <p style={{ color: '#666', marginTop: '16px', fontStyle: 'italic' }}>No tool calls executed in the last request.</p>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '16px', marginTop: '16px' }}>
              <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: '16px' }}>
                <div style={{ backgroundColor: '#111', padding: '12px', borderRadius: '6px', border: '1px solid #222' }}>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>Last Executed Tool</div>
                  <div style={{ fontWeight: 'bold', fontFamily: 'monospace', color: 'var(--color-green)' }}>{last_executed_tool}</div>
                </div>
                <div style={{ backgroundColor: '#111', padding: '12px', borderRadius: '6px', border: '1px solid #222' }}>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>Tool Latency</div>
                  <div style={{ fontWeight: 'bold', fontSize: '16px' }}>{tool_execution_time_ms} ms</div>
                </div>
                <div style={{ backgroundColor: '#111', padding: '12px', borderRadius: '6px', border: '1px solid #222' }}>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>Tool Outcome</div>
                  <div>
                    <span className={`badge ${tool_status === 'success' ? 'success' : 'danger'}`}>
                      {tool_status.toUpperCase()}
                    </span>
                  </div>
                </div>
              </div>

              {tool_output && (
                <div style={{ backgroundColor: '#111', padding: '12px', borderRadius: '6px', border: '1px solid #222' }}>
                  <div style={{ fontSize: '12px', color: '#888', marginBottom: '4px' }}>Sanitized Tool Output</div>
                  <pre style={{ margin: 0, fontFamily: 'monospace', fontSize: '13px', color: '#ccc', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                    {tool_output}
                  </pre>
                </div>
              )}

              {tool_exception && (
                <div style={{ backgroundColor: '#3a1111', padding: '12px', borderRadius: '6px', border: '1px solid #ff5555' }}>
                  <div style={{ fontSize: '12px', color: '#ff8888', marginBottom: '4px', fontWeight: 'bold' }}>Tool Exception raised</div>
                  <div style={{ fontFamily: 'monospace', color: '#ffcccc', fontSize: '13px' }}>{tool_exception}</div>
                </div>
              )}
            </div>
          )}
        </div>

        {/* Row 4: Request Timeline */}
        {renderTimeline()}

        {/* Row 4b: Failure Category Banner (shown only on failed requests) */}
        {failure_category && failure_category !== 'NONE' && last_response_status !== 'success' && (
          <div className="card" style={{ backgroundColor: '#1a0808', border: `1px solid ${getCategoryColor(failure_category)}55` }}>
            <h3 className="card-title" style={{ color: getCategoryColor(failure_category) }}>⚠ Failure Classification</h3>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px', marginTop: '16px' }}>
              <span style={{
                fontSize: '13px', fontFamily: 'monospace', padding: '6px 12px', borderRadius: '6px',
                backgroundColor: getCategoryColor(failure_category) + '22',
                border: `1px solid ${getCategoryColor(failure_category)}`,
                color: getCategoryColor(failure_category),
                fontWeight: 'bold',
              }}>{failure_category}</span>
              <span style={{ color: '#888', fontSize: '13px' }}>This is the backend’s structured failure type for the last request.</span>
            </div>
          </div>
        )}

        {/* Row 5: Raw Provider Request Payload */}
        {last_request_id && last_provider_payload && Object.keys(last_provider_payload).length > 0 && (
          <div className="card">
            <h3 className="card-title">💾 Raw LLM Provider Payload (Sanitized)</h3>
            <div style={{ marginTop: '16px', maxHeight: '350px', overflowY: 'auto', backgroundColor: '#111', border: '1px solid #222', borderRadius: '6px', padding: '12px' }}>
              <pre style={{ margin: 0, fontFamily: 'monospace', fontSize: '12px', color: '#88e088', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                {JSON.stringify(last_provider_payload, null, 2)}
              </pre>
            </div>
          </div>
        )}

        {/* Row 6: Last Exception (if any) */}
        {last_exception && (
          <div className="card" style={{ backgroundColor: '#220808', border: '1px solid #ff4444' }}>
            <h3 className="card-title" style={{ color: '#ff5555' }}>⚠️ Last Pipeline Exception Details</h3>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', marginTop: '16px' }}>
              <div><span style={{ color: '#ff8888', fontSize: '13px' }}>Exception Type: </span><span style={{ fontWeight: 'bold', fontFamily: 'monospace' }}>{last_exception_type}</span></div>
              <pre style={{ margin: 0, padding: '12px', backgroundColor: '#110404', borderRadius: '4px', fontFamily: 'monospace', fontSize: '13px', color: '#ffcccc', whiteSpace: 'pre-wrap', wordBreak: 'break-all' }}>
                {last_exception}
              </pre>
            </div>
          </div>
        )}

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
          <div className={`nav-item ${activeTab === 'model_manager' ? 'active' : ''}`} onClick={() => setActiveTab('model_manager')}>
            🤖 Model Manager
          </div>
          <div className={`nav-item ${activeTab === 'model_benchmarks' ? 'active' : ''}`} onClick={() => setActiveTab('model_benchmarks')}>
            📊 Model Benchmarks
          </div>
          <div className={`nav-item ${activeTab === 'resources' ? 'active' : ''}`} onClick={() => setActiveTab('resources')}>
            📊 Resource Manager
          </div>
          <div className={`nav-item ${activeTab === 'prompt_profiler' ? 'active' : ''}`} onClick={() => setActiveTab('prompt_profiler')}>
            ⚡ Prompt Profiler
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
          <div className={`nav-item ${activeTab === 'diagnostics' ? 'active' : ''}`} onClick={() => { setActiveTab('diagnostics'); fetchDiagnostics(); }}>
            🔬 Diagnostics
          </div>
        </div>

        <div className="sidebar-footer">
          Platform: v0.4.5.2<br />
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
              {activeTab === 'model_manager' && 'Dynamic Model Registry'}
              {activeTab === 'model_benchmarks' && 'AI Model Performance Benchmarks'}
              {activeTab === 'resources' && 'AI Resource Telemetry'}
              {activeTab === 'prompt_profiler' && 'Prompt Optimization Profiler'}
              {activeTab === 'memory' && 'Saved Memory Manager'}
              {activeTab === 'tools' && 'Registered Tools Registry'}
              {activeTab === 'logs' && 'System logs & Diagnostics'}
              {activeTab === 'diagnostics' && 'Developer Diagnostics'}
            </h1>
            <p className="page-subtitle">
              {activeTab === 'home' && 'Live status overview of the Minecraft assistant backend.'}
              {activeTab === 'config' && 'Fine-tune model temperatures, quotas, API keys, and rate limits.'}
              {activeTab === 'model_manager' && 'Switch active LLM models, view context windows, and update rate limits.'}
              {activeTab === 'model_benchmarks' && 'Benchmark latency, success rates, token usage, and tool accuracy side-by-side.'}
              {activeTab === 'resources' && 'Verify input/output token counts, response latency, and hourly usage.'}
              {activeTab === 'prompt_profiler' && 'Analyze LLM prompt composition, optimization statistics, and token savings.'}
              {activeTab === 'memory' && 'Directly inspect and modify locations, notes, and preference indexes.'}
              {activeTab === 'tools' && 'Verify schemas, descriptions, and descriptions of registered tools.'}
              {activeTab === 'logs' && 'Realtime logs aggregated from both launcher and assistant subprocesses.'}
              {activeTab === 'diagnostics' && 'Live request tracing, pipeline stage timings, model capabilities, and exception details.'}
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
        {activeTab === 'model_manager' && renderModelManager()}
        {activeTab === 'model_benchmarks' && renderModelBenchmarks()}
        {activeTab === 'resources' && renderResources()}
        {activeTab === 'prompt_profiler' && renderPromptProfiler()}
        {activeTab === 'memory' && renderMemory()}
        {activeTab === 'tools' && renderTools()}
        {activeTab === 'logs' && renderLogs()}
        {activeTab === 'diagnostics' && renderDiagnostics()}

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
