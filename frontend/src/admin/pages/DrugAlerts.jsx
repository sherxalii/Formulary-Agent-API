import React, { useState, useEffect } from 'react';
import { ShieldAlert, Bell, Filter, CheckCircle2, AlertTriangle, Info, MoreVertical, Search } from 'lucide-react';
import { apiRequest } from '../../utils/auth';

const DrugAlerts = () => {
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState('all');

  useEffect(() => {
    const fetchAlerts = async () => {
      const res = await apiRequest('GET', '/admin/alerts');
      if (res.success) {
        setAlerts(res.alerts);
      }
      setLoading(false);
    };
    fetchAlerts();
  }, []);

  const getSeverityStyle = (severity) => {
    switch(severity) {
      case 'critical': return { icon: <AlertTriangle size={18} />, color: '#ef4444', bg: '#fef2f2' };
      case 'warning': return { icon: <AlertTriangle size={18} />, color: '#f59e0b', bg: '#fffbeb' };
      default: return { icon: <Info size={18} />, color: '#3b82f6', bg: '#eff6ff' };
    }
  };

  const filteredAlerts = alerts.filter(a => filter === 'all' || a.severity === filter);

  if (loading) return <div className="admin-loading">Monitoring clinical triggers...</div>;

  return (
    <div className="animate-fade-in">
      <div className="admin-page-header">
        <div className="header-title">
          <h1>Drug Alerts</h1>
          <p>Monitor and manage critical safety notifications and system warnings.</p>
        </div>
        <div className="header-actions">
          <button className="admin-btn btn-outline">
            <CheckCircle2 size={18} />
            Mark All Read
          </button>
        </div>
      </div>

      <div className="admin-card" style={{ padding: '0' }}>
        <div style={{ padding: '20px', borderBottom: '1px solid var(--admin-divider)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', gap: '8px' }}>
            {['all', 'critical', 'warning', 'info'].map(t => (
              <button 
                key={t} 
                className={`admin-tab-pill ${filter === t ? 'active' : ''}`}
                onClick={() => setFilter(t)}
                style={{ textTransform: 'capitalize' }}
              >
                {t}
              </button>
            ))}
          </div>
          <div className="admin-search-wrapper" style={{ width: '250px' }}>
            <Search size={16} className="search-icon" />
            <input type="text" placeholder="Filter alerts..." className="admin-search-input" />
          </div>
        </div>

        <div className="alerts-list">
          {filteredAlerts.length > 0 ? (
            filteredAlerts.map((alert) => {
              const style = getSeverityStyle(alert.severity);
              return (
                <div key={alert.id} style={{ 
                  display: 'flex', 
                  gap: '16px', 
                  padding: '24px', 
                  borderBottom: '1px solid #f1f5f9',
                  transition: 'background 0.2s'
                }} className="alert-item-hover">
                  <div style={{ 
                    width: '40px', 
                    height: '40px', 
                    borderRadius: '10px', 
                    display: 'flex', 
                    alignItems: 'center', 
                    justifyContent: 'center',
                    background: style.bg,
                    color: style.color,
                    flexShrink: 0
                  }}>
                    {style.icon}
                  </div>
                  <div style={{ flex: 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                      <h4 style={{ fontSize: '1rem', fontWeight: 700, margin: 0, color: 'var(--admin-text-primary)' }}>{alert.title}</h4>
                      <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{alert.time}</span>
                    </div>
                    <p style={{ fontSize: '0.9rem', color: '#64748b', margin: '6px 0 16px', lineHeight: 1.5 }}>{alert.msg}</p>
                    <div style={{ display: 'flex', gap: '12px' }}>
                      <button className="admin-btn btn-primary" style={{ padding: '6px 16px', fontSize: '0.8rem' }}>Resolve</button>
                      <button className="admin-btn btn-outline" style={{ padding: '6px 16px', fontSize: '0.8rem' }}>View Clinical Context</button>
                    </div>
                  </div>
                  <button className="topbar-action-btn" style={{ alignSelf: 'flex-start' }}>
                    <MoreVertical size={18} />
                  </button>
                </div>
              );
            })
          ) : (
            <div style={{ padding: '80px', textAlign: 'center', color: '#94a3b8' }}>
              <CheckCircle2 size={48} style={{ margin: '0 auto 16px', opacity: 0.2 }} />
              <p>No active alerts found for this category.</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default DrugAlerts;
