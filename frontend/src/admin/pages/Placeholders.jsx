import React, { useState, useEffect } from 'react';
import { 
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, 
  LineChart, Line, AreaChart, Area, Cell, PieChart, Pie
} from 'recharts';
import { 
  Shield, Clock, Search, Save, Globe, Lock, Bell, 
  ShieldAlert, FileText, Activity as ActivityIcon, Edit,
  Download, RefreshCcw, CheckCircle2, AlertTriangle, Key,
  Smartphone, Mail, MessageSquare, Database, Cpu,
  User, Sun, ChevronRight, Activity, Zap, Trash2, 
  Monitor, MapPin, RotateCw, Terminal, Plus, Eye, EyeOff
} from 'lucide-react';
import { getCurrentUser, apiRequest } from '../../utils/auth';
import toast from 'react-hot-toast';

// ─── Analytics Page ─────────────────────────────────────────────────────────
export const Analytics = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchAnalytics = async () => {
      const res = await apiRequest('GET', '/dashboard/stats');
      if (res.success) {
        setData(res);
      }
      setLoading(false);
    };
    fetchAnalytics();
  }, []);

  if (loading) return <div className="admin-loading">Crunching platform metrics...</div>;

  const metricCards = [
    { label: 'Total Inquiries', value: data?.metrics?.totalDrugs?.toLocaleString(), icon: Search, color: '#7047ee' },
    { label: 'System Accuracy', value: `${data?.metrics?.modelAccuracy}%`, icon: CheckCircle2, color: '#10b981' },
    { label: 'Pending Alerts', value: data?.metrics?.drugAlerts, icon: AlertTriangle, color: '#f59e0b' },
    { label: 'Active Sessions', value: data?.metrics?.activeUsers, icon: ActivityIcon, color: '#3b82f6' }
  ];

  return (
    <div className="animate-fade-in">
      <div className="admin-page-header">
        <div className="header-title">
          <h1>Platform Analytics</h1>
          <p>Deep-dive into system usage and clinical data performance.</p>
        </div>
      </div>

      <div className="admin-metrics-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: '24px' }}>
        {metricCards.map((m, i) => (
          <div key={i} className="admin-metric-card">
            <div className="metric-header">
              <m.icon size={20} style={{ color: m.color }} />
              <span className="metric-label">{m.label}</span>
            </div>
            <div className="metric-value">{m.value}</div>
          </div>
        ))}
      </div>

      <div className="admin-dashboard-grid">
        <div className="admin-card">
          <div className="admin-card-header">
            <h3>Search Volume (Last 7 Days)</h3>
          </div>
          <div style={{ height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={data?.searchTraffic || []}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7047ee" stopOpacity={0.1}/>
                    <stop offset="95%" stopColor="#7047ee" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="day" axisLine={false} tickLine={false} />
                <YAxis axisLine={false} tickLine={false} />
                <Tooltip contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 4px 6px -1px rgb(0 0 0 / 0.1)' }} />
                <Area type="monotone" dataKey="count" stroke="#7047ee" strokeWidth={3} fillOpacity={1} fill="url(#colorCount)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="admin-card">
          <div className="admin-card-header">
            <h3>Top Therapeutic Classes</h3>
          </div>
          <div style={{ height: '300px' }}>
            <ResponsiveContainer width="100%" height="100%">
              <BarChart data={data?.topDrugs || []} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" horizontal={false} stroke="#f1f5f9" />
                <XAxis type="number" hide />
                <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} width={100} />
                <Tooltip cursor={{ fill: '#f8fafc' }} contentStyle={{ borderRadius: '12px', border: 'none' }} />
                <Bar dataKey="count" fill="#3b82f6" radius={[0, 4, 4, 0]} barSize={20} />
              </BarChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
};

// ─── Audit Logs Page ────────────────────────────────────────────────────────
export const AuditLogs = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [filter, setFilter] = useState('All');
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchLogs = async () => {
      const res = await apiRequest('GET', '/admin/logs');
      if (res.success) {
        setData(res);
      }
      setLoading(false);
    };
    fetchLogs();
  }, []);

  if (loading) return <div className="admin-loading">Accessing secure audit trails...</div>;

  const filteredLogs = (data?.logs || []).filter(log => {
    const matchesSearch = log.action.toLowerCase().includes(searchTerm.toLowerCase()) || 
                         log.target.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         log.user.toLowerCase().includes(searchTerm.toLowerCase());
    const matchesFilter = filter === 'All' || log.status === filter;
    return matchesSearch && matchesFilter;
  });

  return (
    <div className="animate-fade-in">
      <div className="admin-page-header">
        <div className="header-title">
          <h1>Security Audit Logs</h1>
          <p>Real-time traceability for all administrative actions.</p>
        </div>
        <div className="admin-actions">
          <button className="admin-btn btn-outline" onClick={() => window.print()}>
            <FileText size={18} />
            Export Report
          </button>
        </div>
      </div>

      <div className="admin-metrics-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: '24px' }}>
        <div className="admin-metric-card">
          <div className="metric-header">
            <Shield size={20} className="text-success" />
            <span className="metric-label">Total Events</span>
          </div>
          <div className="metric-value">{data?.stats?.total?.toLocaleString() ?? '0'}</div>
        </div>
        <div className="admin-metric-card">
          <div className="metric-header">
            <ActivityIcon size={20} className="text-info" />
            <span className="metric-label">System Activity</span>
          </div>
          <div className="metric-value">{data?.stats?.activity ?? 'Stable'}</div>
        </div>
        <div className="admin-metric-card">
          <div className="metric-header">
            <Lock size={20} className="text-warning" />
            <span className="metric-label">Sec. Alerts</span>
          </div>
          <div className="metric-value">{data?.stats?.alerts ?? '0'}</div>
        </div>
        <div className="admin-metric-card">
          <div className="metric-header">
            <ShieldAlert size={20} className="text-danger" />
            <span className="metric-label">Blocked</span>
          </div>
          <div className="metric-value">{data?.stats?.blocked ?? '0'}</div>
        </div>
      </div>

      <div className="admin-card" style={{ padding: '0' }}>
        <div style={{ padding: '20px', borderBottom: '1px solid var(--admin-divider)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            {['All', 'Success', 'Warning', 'Blocked'].map(tab => (
              <button 
                key={tab} 
                className={`admin-tab-pill ${filter === tab ? 'active' : ''}`}
                onClick={() => setFilter(tab)}
              >
                {tab}
              </button>
            ))}
          </div>
          <div className="admin-search-wrapper" style={{ width: '300px' }}>
            <Search size={18} className="search-icon" />
            <input 
              type="text" 
              placeholder="Search logs..." 
              className="admin-search-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
        </div>

        <div className="admin-table-container">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Action Details</th>
                <th className="hide-on-mobile">Entity</th>
                <th>Triggered By</th>
                <th className="hide-on-mobile">Timestamp</th>
                <th>Outcome</th>
              </tr>
            </thead>
            <tbody>
              {filteredLogs.length > 0 ? filteredLogs.map(log => (
                <tr key={log.id}>
                  <td>
                    <div style={{ fontWeight: 700, color: 'var(--admin-text-primary)' }}>{log.action}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--admin-text-muted)' }}>{log.type} Event</div>
                  </td>
                  <td className="hide-on-mobile">{log.target}</td>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <div className="admin-avatar-small" style={{ 
                        width: '24px', 
                        height: '24px', 
                        fontSize: '10px',
                        background: log.color || 'var(--admin-primary)'
                      }}>
                        {log.user[0]}
                      </div>
                      <span style={{ fontWeight: 600 }}>{log.user}</span>
                    </div>
                  </td>
                  <td className="hide-on-mobile" style={{ color: 'var(--admin-text-muted)', fontSize: '0.85rem' }}>{log.time}</td>
                  <td>
                    <span className={`admin-badge ${
                      log.status === 'Success' ? 'badge-success' : 
                      log.status === 'Warning' ? 'badge-warning' : 'badge-danger'
                    }`}>
                      {log.status}
                    </span>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '80px 20px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', color: 'var(--admin-text-muted)' }}>
                      <Search size={40} style={{ opacity: 0.2 }} />
                      <p style={{ margin: 0, fontSize: '0.95rem' }}>No audit logs match your current search criteria.</p>
                      <button className="admin-btn btn-outline" style={{ fontSize: '0.8rem', padding: '6px 12px' }} onClick={() => {setSearchTerm(''); setFilter('All');}}>Clear Filters</button>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ─── Admin Settings Page ──────────────────────────────────────────────────
export const AdminSettings = () => {
  const [activeTab, setActiveTab] = useState('Account Profile');
  const [loading, setLoading] = useState(false);
  const [toggles, setToggles] = useState({
    twoFactor: true,
    maintenance: false,
    phiAnonymization: true,
    cookieManager: false,
    notifications: { email: true, push: true, security: true }
  });

  const [sessions, setSessions] = useState([]);
  const [apiKeys, setApiKeys] = useState([]);
  const [revealedKeys, setRevealedKeys] = useState({});

  const user = getCurrentUser() || { 
    name: 'Sher Ali', 
    email: 'sheryy8002@gmail.com', 
    role: 'Admin',
    department: 'General'
  };

  useEffect(() => {
    if (activeTab === 'Security Settings') fetchSessions();
    if (activeTab === 'Advanced') fetchApiKeys();
  }, [activeTab]);

  const fetchSessions = async () => {
    const res = await apiRequest('GET', '/admin/security/sessions');
    if (res.success) setSessions(res.sessions);
  };

  const fetchApiKeys = async () => {
    const res = await apiRequest('GET', '/admin/api-keys');
    if (res.success) setApiKeys(res.keys);
  };

  const handleSaveProfile = async () => {
    setLoading(true);
    const res = await apiRequest('POST', '/admin/profile/update', { name: user.name });
    if (res.success) {
      toast.success('Profile updated successfully!');
    } else {
      toast.error('Failed to update profile.');
    }
    setLoading(false);
  };

  const handleToggleSetting = async (key, currentVal) => {
    const newVal = !currentVal;
    const res = await apiRequest('POST', '/admin/settings/toggle', { key, enabled: newVal });
    if (res.success) {
      setToggles(prev => ({ ...prev, [key]: newVal }));
      toast.success(`${key.charAt(0).toUpperCase() + key.slice(1).replace(/([A-Z])/g, ' $1')} ${newVal ? 'enabled' : 'disabled'}`);
    } else {
      toast.error('Failed to update system setting.');
    }
  };

  const handleToggleMaintenance = async () => {
    const newState = !toggles.maintenance;
    const res = await apiRequest('POST', '/admin/maintenance', { enabled: newState });
    if (res.success) {
      setToggles(prev => ({ ...prev, maintenance: newState }));
      toast.success(`Maintenance mode ${newState ? 'enabled' : 'disabled'}`);
    }
  };

  const handleLogoutSession = async (sid) => {
    const res = await apiRequest('POST', '/admin/security/logout-session', { session_id: sid });
    if (res.success) {
      setSessions(prev => prev.filter(s => s.id !== sid));
      toast.success('Session terminated.');
    }
  };

  const handleRevokeKey = async (kid) => {
    const res = await apiRequest('DELETE', `/admin/api-keys/${kid}`);
    if (res.success) {
      setApiKeys(prev => prev.filter(k => k.id !== kid));
      toast.success('API Key revoked.');
    }
  };

  const handleCreateKey = async () => {
    const name = window.prompt("Enter a name for the new API key:");
    if (!name) return;
    const res = await apiRequest('POST', '/admin/api-keys', { name });
    if (res.success) {
      setApiKeys(prev => [...prev, res.key]);
      toast.success('New API Key generated.');
    }
  };

  const toggleKeyReveal = (id) => {
    setRevealedKeys(prev => ({ ...prev, [id]: !prev[id] }));
  };

  const handleReindex = async () => {
    toast.loading('Initializing re-index...', { id: 'reindex' });
    const res = await apiRequest('POST', '/admin/reindex');
    if (res.success) {
      toast.success('RAG Indexing started in background.', { id: 'reindex' });
    } else {
      toast.error('Re-indexing failed to start.', { id: 'reindex' });
    }
  };

  const tabs = [
    { name: 'Account Profile', icon: User },
    { name: 'Security Settings', icon: Lock },
    { name: 'Preferences', icon: Sun },
    { name: 'Privacy & Cookies', icon: Shield },
    { name: 'Advanced', icon: Activity }
  ];

  const renderTabContent = () => {
    switch (activeTab) {
      case 'Account Profile':
        return (
          <div className="animate-fade-in">
            <div className="settings-main-header">
              <h2>Account Profile</h2>
              <p>Update your personal details and role information.</p>
            </div>

            <div className="profile-highlight-card">
              <div className="profile-main-info">
                <div className="profile-square-avatar">
                  {user.name.split(' ').map(n => n[0]).join('')}
                </div>
                <div className="profile-text-info">
                  <h3>{user.name}</h3>
                  <p>{user.email}</p>
                  <div className="role-badge-teal">{user.role}</div>
                </div>
              </div>
              <button className="btn-teal-outline">Change Photo</button>
            </div>

            <div className="settings-form-grid">
              <div className="form-group">
                <label>Full Name</label>
                <input type="text" className="form-input-teal" defaultValue={user.name} />
              </div>
              <div className="form-group">
                <label>Email Address</label>
                <input type="email" className="form-input-teal" defaultValue={user.email} />
              </div>
              <div className="form-group">
                <label>Department</label>
                <input type="text" className="form-input-teal" defaultValue={user.department} />
              </div>
              <div className="form-group">
                <label>Role (read-only)</label>
                <input type="text" className="form-input-teal" defaultValue={user.role} disabled />
              </div>
            </div>

            <button 
              className="btn-teal-save" 
              onClick={handleSaveProfile}
              disabled={loading}
            >
              {loading ? 'Saving...' : 'Save Changes'}
            </button>
          </div>
        );
      case 'Security Settings':
        return (
          <div className="animate-fade-in">

            <div className="settings-main-header">
              <h2>Security Settings</h2>
              <p>Manage your account security, password, and active sessions.</p>
            </div>

            {!toggles.twoFactor && (
              <div style={{ 
                background: '#fff7ed', 
                border: '1px solid #ffedd5', 
                borderRadius: '16px', 
                padding: '16px 24px', 
                display: 'flex', 
                alignItems: 'center', 
                gap: '16px',
                marginBottom: '32px',
                animation: 'slideDown 0.3s ease-out'
              }}>
                <div style={{ background: '#ffedd5', padding: '10px', borderRadius: '12px', color: '#ea580c' }}>
                  <ShieldAlert size={20} />
                </div>
                <div style={{ flex: 1 }}>
                  <h4 style={{ margin: '0 0 2px', fontSize: '0.95rem', fontWeight: 700, color: '#9a3412' }}>Action Required: Enable 2FA</h4>
                  <p style={{ margin: 0, fontSize: '0.85rem', color: '#c2410c' }}>Your account is currently less secure. Enable Two-Factor Authentication to protect clinical data.</p>
                </div>
                <button 
                  className="btn-teal-outline" 
                  style={{ border: '1px solid #fb923c', color: '#ea580c', whiteSpace: 'nowrap' }}
                  onClick={() => handleToggleSetting('twoFactor', toggles.twoFactor)}
                >
                  Enable Now
                </button>
              </div>
            )}



            <div className="profile-highlight-card" style={{ marginBottom: '32px' }}>
              <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                <div className="hipaa-icon-box" style={{ marginBottom: 0 }}>
                  <Smartphone size={20} />
                </div>
                <div>
                  <h4 style={{ margin: '0 0 4px', fontSize: '1rem', fontWeight: 700 }}>Two-Factor Authentication</h4>
                  <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>Secure your account with a secondary verification step.</p>
                </div>
              </div>
              <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                <span style={{ fontSize: '0.85rem', fontWeight: 600, color: toggles.twoFactor ? '#10b981' : '#94a3b8' }}>
                  {toggles.twoFactor ? 'Enabled' : 'Disabled'}
                </span>
                <div 
                  className={`st-toggle ${toggles.twoFactor ? 'active' : ''}`}
                  onClick={() => handleToggleSetting('twoFactor', toggles.twoFactor)}
                  style={{ cursor: 'pointer' }}
                ></div>
              </div>
            </div>


            <h4 style={{ fontSize: '0.75rem', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '16px' }}>Active Sessions</h4>
            <div style={{ border: '1px solid #f1f5f9', borderRadius: '16px', overflow: 'hidden' }}>
              {sessions.map(s => (
                <div key={s.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: s.id !== sessions.length ? '1px solid #f1f5f9' : 'none' }}>
                  <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                    <Monitor size={20} style={{ color: '#64748b' }} />
                    <div>
                      <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{s.device} {s.is_current && <span className="role-badge-teal" style={{ fontSize: '0.65rem', marginLeft: '8px' }}>Current</span>}</div>
                      <div style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{s.location} • {s.ip}</div>
                    </div>
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                    <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{s.last_active}</span>
                    {!s.is_current && <button className="btn-teal-outline" onClick={() => handleLogoutSession(s.id)} style={{ padding: '6px 12px', fontSize: '0.75rem' }}>Logout</button>}
                  </div>
                </div>
              ))}
            </div>
          </div>
        );
      case 'Preferences':
        return (
          <div className="animate-fade-in">
            <div className="settings-main-header">
              <h2>User Preferences</h2>
              <p>Personalize your administrative dashboard experience.</p>
            </div>

            <div className="settings-form-grid">
              <div className="form-group">
                <label>Interface Language</label>
                <select className="form-input-teal">
                  <option>English (US)</option>
                  <option>Spanish</option>
                  <option>French</option>
                  <option>German</option>
                </select>
              </div>
              <div className="form-group">
                <label>Timezone</label>
                <select className="form-input-teal">
                  <option>GMT+0 (Leeds/London)</option>
                  <option>UTC-5 (New York)</option>
                  <option>UTC+1 (Paris/Berlin)</option>
                </select>
              </div>
            </div>

            <h4 style={{ fontSize: '0.75rem', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', marginBottom: '20px' }}>Notification Channels</h4>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
              {[
                { label: 'Email Alerts', key: 'email', icon: Mail },
                { label: 'SMS Notifications', key: 'push', icon: MessageSquare },
                { label: 'System Push Notifications', key: 'security', icon: Bell }
              ].map(item => (
                <div key={item.key} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div style={{ display: 'flex', gap: '16px', alignItems: 'center' }}>
                    <item.icon size={18} style={{ color: '#10b981' }} />
                    <span style={{ fontWeight: 600, fontSize: '0.95rem' }}>{item.label}</span>
                  </div>
                  <div 
                    className={`st-toggle ${toggles.notifications[item.key] ? 'active' : ''}`}
                    onClick={() => setToggles(prev => ({ 
                      ...prev, 
                      notifications: { ...prev.notifications, [item.key]: !prev.notifications[item.key] } 
                    }))}
                    style={{ cursor: 'pointer' }}
                  ></div>
                </div>
              ))}
            </div>
          </div>
        );
      case 'Privacy & Cookies':
        return (
          <div className="animate-fade-in">
            <div className="settings-main-header">
              <h2>Privacy Control</h2>
              <p>Configure data retention policies and clinical privacy measures.</p>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '24px' }}>
              <div className="profile-highlight-card" style={{ marginBottom: 0, padding: '24px' }}>
                <div>
                  <h4 style={{ margin: '0 0 4px', fontSize: '1rem', fontWeight: 700 }}>PHI Anonymization</h4>
                  <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>Automatically strip patient-identifiable data from search logs.</p>
                </div>
                <div 
                  className={`st-toggle ${toggles.phiAnonymization ? 'active' : ''}`}
                  onClick={() => handleToggleSetting('phiAnonymization', toggles.phiAnonymization)}
                  style={{ cursor: 'pointer' }}
                ></div>
              </div>

              <div className="form-group">
                <label>Audit Log Retention Policy</label>
                <div style={{ display: 'flex', gap: '12px' }}>
                  {['30 Days', '90 Days', '1 Year', 'Forever'].map(t => (
                    <button 
                      key={t} 
                      className={`admin-tab-pill ${t === '90 Days' ? 'active' : ''}`}
                      style={{ padding: '10px 20px', borderRadius: '12px' }}
                    >
                      {t}
                    </button>
                  ))}
                </div>
              </div>

              <div className="profile-highlight-card" style={{ marginBottom: 0, padding: '24px' }}>
                <div>
                  <h4 style={{ margin: '0 0 4px', fontSize: '1rem', fontWeight: 700 }}>Cookie Consent Manager</h4>
                  <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>Show mandatory compliance banner for all European traffic.</p>
                </div>
                <div 
                  className={`st-toggle ${toggles.cookieManager ? 'active' : ''}`}
                  onClick={() => handleToggleSetting('cookieManager', toggles.cookieManager)}
                  style={{ cursor: 'pointer' }}
                ></div>
              </div>
            </div>
          </div>
        );
      case 'Advanced':
        return (
          <div className="animate-fade-in">
            <div className="settings-main-header">
              <h2>Advanced Engine Config</h2>
              <p>Low-level system controls, API management, and indexing.</p>
            </div>

            <div className="settings-form-grid" style={{ marginBottom: '32px' }}>
              <div className="profile-highlight-card" style={{ marginBottom: 0, gridColumn: 'span 2', background: toggles.maintenance ? '#fffbeb' : 'white' }}>
                <div style={{ display: 'flex', gap: '20px', alignItems: 'center' }}>
                  <div className="hipaa-icon-box" style={{ marginBottom: 0, background: toggles.maintenance ? '#fef3c7' : '#f0fdf4', color: toggles.maintenance ? '#d97706' : '#10b981' }}>
                    <Zap size={20} />
                  </div>
                  <div>
                    <h4 style={{ margin: '0 0 4px', fontSize: '1rem', fontWeight: 700 }}>Maintenance Mode</h4>
                    <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>Disable public searches while performing database upgrades.</p>
                  </div>
                </div>
                <div 
                  className={`st-toggle ${toggles.maintenance ? 'active' : ''}`}
                  onClick={handleToggleMaintenance}
                  style={{ cursor: 'pointer' }}
                ></div>
              </div>
            </div>

            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
              <h4 style={{ fontSize: '0.75rem', fontWeight: 800, color: '#94a3b8', textTransform: 'uppercase', margin: 0 }}>Clinical API Keys</h4>
              <button className="btn-teal-outline" onClick={handleCreateKey} style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '8px 16px' }}>
                <Plus size={16} /> New Key
              </button>
            </div>

            <div style={{ border: '1px solid #f1f5f9', borderRadius: '16px', overflow: 'hidden', marginBottom: '32px' }}>
              {apiKeys.length > 0 ? apiKeys.map(k => (
                <div key={k.id} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '16px 20px', borderBottom: k.id !== apiKeys.length ? '1px solid #f1f5f9' : 'none' }}>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: '0.9rem' }}>{k.name}</div>
                    <div style={{ fontSize: '0.85rem', color: '#94a3b8', fontFamily: 'monospace', marginTop: '4px' }}>
                      {revealedKeys[k.id] ? k.key : 'med_pk_live_******************'}
                    </div>
                  </div>
                  <div style={{ display: 'flex', gap: '12px' }}>
                    <button className="topbar-action-btn" onClick={() => toggleKeyReveal(k.id)}>
                      {revealedKeys[k.id] ? <EyeOff size={18} /> : <Eye size={18} />}
                    </button>
                    <button className="topbar-action-btn" onClick={() => handleRevokeKey(k.id)} style={{ color: '#ef4444' }}>
                      <Trash2 size={18} />
                    </button>
                  </div>
                </div>
              )) : (
                <div style={{ padding: '24px', textAlign: 'center', color: '#94a3b8', fontSize: '0.9rem' }}>No API keys generated yet.</div>
              )}
            </div>

            <div className="profile-highlight-card" style={{ padding: '32px' }}>
              <div>
                <h4 style={{ margin: '0 0 4px', fontSize: '1rem', fontWeight: 700 }}>Global Vector Re-indexing</h4>
                <p style={{ margin: 0, fontSize: '0.85rem', color: '#64748b' }}>Force a complete refresh of the RAG drug database embeddings.</p>
              </div>
              <button 
                className="btn-teal-save" 
                style={{ margin: 0, display: 'flex', gap: '10px' }}
                onClick={handleReindex}
              >
                <RotateCw size={18} />
                Re-index Now
              </button>
            </div>
          </div>
        );
      default:
        return null;
    }
  };

  return (
    <div className="animate-fade-in" style={{ padding: '0 8px' }}>
      <div className="settings-layout">
        <div className="settings-sidebar">
          <div className="settings-nav-card">
            {tabs.map(tab => (
              <button 
                key={tab.name} 
                className={`settings-nav-item ${activeTab === tab.name ? 'active' : ''}`}
                onClick={() => setActiveTab(tab.name)}
              >
                <div className="nav-left">
                  <tab.icon size={20} />
                  <span>{tab.name}</span>
                </div>
                <ChevronRight size={16} className="chevron" />
              </button>
            ))}
          </div>

          <div className="hipaa-card">
            <div className="hipaa-icon-box">
              <Shield size={20} />
            </div>
            <h5>HIPAA Compliant</h5>
            <p>Your data is encrypted and stored in compliance with all applicable healthcare regulations.</p>
          </div>
        </div>

        <div className="settings-main-container">
          {renderTabContent()}
        </div>
      </div>
    </div>
  );
};

// ─── Formulary Plans Page ──────────────────────────────────────────────────
export const FormularyPlans = () => {
  const [plans, setPlans] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchPlans = async () => {
      const res = await apiRequest('GET', '/admin/plans');
      if (res.success) setPlans(res.plans);
      setLoading(false);
    };
    fetchPlans();
  }, []);

  return (
    <div className="animate-fade-in">
      <div className="admin-page-header">
        <div className="header-title">
          <h1>Formulary Plans</h1>
          <p>Manage insurance coverage and tier logic sync status.</p>
        </div>
        <button className="admin-btn btn-primary">
          <RefreshCcw size={18} /> Sync All Plans
        </button>
      </div>

      <div className="admin-card" style={{ padding: '0' }}>
        <div className="admin-table-container">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Plan Name</th>
                <th>Coverage Tiers</th>
                <th>Last Synchronized</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {loading ? (
                <tr><td colSpan="5" style={{ textAlign: 'center', padding: '40px' }}>Loading plans...</td></tr>
              ) : plans.map(plan => (
                <tr key={plan.id}>
                  <td style={{ fontWeight: 700 }}>{plan.name}</td>
                  <td>{plan.tier_count} Tiers</td>
                  <td style={{ color: '#64748b' }}>{plan.last_sync}</td>
                  <td>
                    <span className={`admin-badge ${plan.status === 'Active' ? 'badge-success' : 'badge-warning'}`}>
                      {plan.status}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="admin-btn btn-outline" style={{ fontSize: '0.8rem', padding: '4px 10px' }}>Details</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};

// ─── Model Performance Page ────────────────────────────────────────────────
export const ModelPerformance = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchData = async () => {
      const res = await apiRequest('GET', '/admin/models');
      if (res.success) setData(res);
      setLoading(false);
    };
    fetchData();
  }, []);

  if (loading) return <div className="admin-loading">Profiling AI models...</div>;

  return (
    <div className="animate-fade-in">
      <div className="admin-page-header">
        <div className="header-title">
          <h1>Model Performance</h1>
          <p>Track clinical safety engine metrics, accuracy trends, and system latency.</p>
        </div>
      </div>

      <div className="admin-metrics-grid" style={{ gridTemplateColumns: 'repeat(4, 1fr)', marginBottom: '24px' }}>
        <div className="admin-metric-card">
          <div className="metric-header">
            <CheckCircle2 size={20} className="text-success" />
            <span className="metric-label">Model Accuracy</span>
          </div>
          <div className="metric-value">{data?.current?.accuracy}%</div>
        </div>
        <div className="admin-metric-card">
          <div className="metric-header">
            <Clock size={20} className="text-info" />
            <span className="metric-label">Avg. Latency</span>
          </div>
          <div className="metric-value">{data?.current?.latency}</div>
        </div>
        <div className="admin-metric-card">
          <div className="metric-header">
            <Globe size={20} className="text-primary" />
            <span className="metric-label">System Uptime</span>
          </div>
          <div className="metric-value">{data?.current?.uptime}</div>
        </div>
        <div className="admin-metric-card">
          <div className="metric-header">
            <Cpu size={20} className="text-warning" />
            <span className="metric-label">Total Inferences</span>
          </div>
          <div className="metric-value">{data?.current?.usage.toLocaleString()}</div>
        </div>
      </div>

      <div className="admin-card">
        <div className="admin-card-header">
          <h3>Accuracy Trend (Last 14 Days)</h3>
        </div>
        <div style={{ height: '300px' }}>
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={data?.history || []}>
              <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
              <XAxis dataKey="date" hide />
              <YAxis domain={[95, 100]} axisLine={false} tickLine={false} />
              <Tooltip contentStyle={{ borderRadius: '12px', border: 'none' }} />
              <Line type="monotone" dataKey="accuracy" stroke="#7047ee" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 6 }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};
