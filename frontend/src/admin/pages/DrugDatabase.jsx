import React, { useState, useEffect } from 'react';
import { Database, Search, Filter, Pill, AlertTriangle, Layout, Download, Plus, MoreHorizontal, Star, AlertCircle } from 'lucide-react';
import { apiRequest } from '../../utils/auth';

const DrugDatabase = () => {
  const [drugs, setDrugs] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  useEffect(() => {
    const fetchDrugs = async () => {
      const res = await apiRequest('GET', '/admin/drugs');
      if (res.success) {
        setDrugs(res.drugs);
        setStats(res.stats);
      } else {
        setError('Failed to synchronize with clinical database. Check backend connectivity.');
      }
      setLoading(false);
    };
    fetchDrugs();
  }, []);

  const getPregnancyBadge = (cat) => {
    const colors = {
      'A': 'badge-success',
      'B': 'badge-success',
      'C': 'badge-warning',
      'D': 'badge-danger',
      'X': 'badge-danger'
    };
    return colors[cat] || 'badge-info';
  };

  if (loading) return (
    <div className="admin-loading-container">
      <div className="admin-loading-spinner"></div>
      <p>Synchronizing clinical data repository...</p>
    </div>
  );

  if (error) return (
    <div className="admin-error-card">
      <AlertCircle size={48} className="text-danger" />
      <h3>Database Connection Error</h3>
      <p>{error}</p>
      <button className="admin-btn btn-primary" onClick={() => window.location.reload()}>Reconnect</button>
    </div>
  );

  const statCards = [
    { label: 'Total Medications', value: stats?.totalDrugs?.toLocaleString() ?? '0', icon: Pill, color: '#7047ee' },
    { label: 'Medical Conditions', value: stats?.drugClasses ?? '0', icon: Database, color: '#10b981' },
    { label: 'Avg Side Effects', value: stats?.avgSideEffects ?? '0', icon: AlertTriangle, color: '#f59e0b' },
    { label: 'Engine Version', value: stats?.version ?? 'N/A', icon: Layout, color: '#3b82f6' }
  ];

  const filteredDrugs = drugs.filter(d => 
    (d.name && d.name.toLowerCase().includes(searchQuery.toLowerCase())) || 
    (d.generic && d.generic.toLowerCase().includes(searchQuery.toLowerCase())) ||
    (d.class && d.class.toLowerCase().includes(searchQuery.toLowerCase()))
  );

  return (
    <div className="animate-fade-in">
      <div className="admin-page-header">
        <div className="header-title">
          <h1>Clinical Drug Database</h1>
          <p>Validated medication records and pharmacological data.</p>
        </div>
        <div style={{ display: 'flex', gap: '12px' }}>
          <button className="admin-btn btn-outline" onClick={() => window.print()}>
            <Download size={18} />
            Export Data
          </button>
          <button className="admin-btn btn-primary">
            <Plus size={18} />
            Add Medication
          </button>
        </div>
      </div>

      <div className="admin-metrics-grid">
        {statCards.map((card, i) => (
          <div key={i} className="admin-card admin-metric-card">
            <div className="metric-icon-box" style={{ backgroundColor: `${card.color}15`, color: card.color }}>
              <card.icon size={24} />
            </div>
            <div className="metric-info">
              <h4>{card.label}</h4>
              <div className="metric-value">{card.value}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="admin-card">
        <div className="admin-card-header">
          <div className="admin-search-wrapper" style={{ width: '400px' }}>
            <Search size={18} className="search-icon" />
            <input 
              type="text" 
              placeholder="Search by name, generic, or drug class..." 
              className="admin-search-input"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
          </div>
          <button className="admin-btn btn-outline">
            <Filter size={18} />
            Advanced Filter
          </button>
        </div>

        <div className="admin-table-container">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Medication</th>
                <th className="hide-on-mobile">Pharmacology</th>
                <th style={{ textAlign: 'center' }}>Safety Cat.</th>
                <th style={{ textAlign: 'center' }}>Type</th>
                <th className="hide-on-mobile">Clinical Rating</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredDrugs.length > 0 ? filteredDrugs.map((drug, i) => (
                <tr key={i}>
                  <td>
                    <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--admin-text-primary)' }}>{drug.name}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--admin-text-muted)' }}>{drug.generic}</div>
                  </td>
                  <td className="hide-on-mobile">
                    <div style={{ fontWeight: 600, fontSize: '0.9rem', color: 'var(--admin-text-primary)' }}>{drug.class}</div>
                    <div style={{ fontSize: '0.8rem', color: 'var(--admin-text-muted)' }}>{drug.condition}</div>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <span className={`admin-badge ${getPregnancyBadge(drug.pregnancy)}`} style={{ width: '32px', height: '32px', borderRadius: '50%', justifyContent: 'center', padding: 0 }}>
                      {drug.pregnancy}
                    </span>
                  </td>
                  <td style={{ textAlign: 'center' }}>
                    <span className={`admin-badge ${drug.type === 'OTC' ? 'badge-info' : 'badge-success'}`}>
                      {drug.type}
                    </span>
                  </td>
                  <td className="hide-on-mobile">
                    <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                      <div style={{ display: 'flex', color: '#f59e0b' }}>
                        {[...Array(5)].map((_, idx) => (
                          <Star key={idx} size={14} fill={idx < Math.floor(drug.rating/2) ? "#f59e0b" : "none"} />
                        ))}
                      </div>
                      <span style={{ fontWeight: 700, fontSize: '0.9rem', color: 'var(--admin-text-primary)' }}>{drug.rating}</span>
                      <span style={{ fontSize: '0.75rem', color: 'var(--admin-text-muted)' }}>({drug.reviews.toLocaleString()})</span>
                    </div>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="topbar-action-btn">
                      <MoreHorizontal size={18} />
                    </button>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="6" style={{ textAlign: 'center', padding: '60px', color: 'var(--admin-text-muted)' }}>
                    No medications found in the database.
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

export default DrugDatabase;
