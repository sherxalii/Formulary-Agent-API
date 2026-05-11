import React, { useState, useEffect } from 'react';
import { Pill, Users, Target, Bell, ArrowUpRight, ArrowDownRight, TrendingUp, Activity, FileText } from 'lucide-react';
import { AreaChart, Area, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, BarChart, Bar, Cell } from 'recharts';
import { apiRequest } from '../../utils/auth';

const Dashboard = () => {
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    const fetchStats = async () => {
      const res = await apiRequest('GET', '/dashboard/stats');
      if (res.success) {
        setStats(res);
      } else {
        setError('Failed to fetch real-time statistics.');
      }
      setLoading(false);
    };
    fetchStats();
  }, []);

  if (loading) return (
    <div className="admin-loading-container">
      <div className="admin-loading-spinner"></div>
      <p>Syncing production metrics...</p>
    </div>
  );

  if (error) return (
    <div className="admin-error-card">
      <Bell size={48} className="text-danger" />
      <h3>System Sync Error</h3>
      <p>{error}</p>
      <button className="admin-btn btn-primary" onClick={() => window.location.reload()}>Retry Connection</button>
    </div>
  );

  const metrics = [
    { label: 'Total Drugs', value: stats?.metrics?.totalDrugs?.toLocaleString() ?? '0', trend: '+12.5%', icon: Pill, color: '#7047ee', trendUp: true },
    { label: 'Active Users', value: stats?.metrics?.activeUsers?.toLocaleString() ?? '0', trend: '+5.2%', icon: Users, color: '#10b981', trendUp: true },
    { label: 'Model Accuracy', value: `${stats?.metrics?.modelAccuracy ?? '98.5'}%`, trend: '+0.4%', icon: Target, color: '#f59e0b', trendUp: true },
    { label: 'Critical Alerts', value: stats?.metrics?.drugAlerts ?? '0', trend: '-2.1%', icon: Bell, color: '#ef4444', trendUp: false },
  ];

  return (
    <div className="animate-fade-in">
      <div className="admin-page-header">
        <div className="header-title">
          <h1>Dashboard Overview</h1>
          <p>Real-time insights and platform performance for MediFormulary.</p>
        </div>
        <div className="header-actions">
          <button className="admin-btn btn-outline" onClick={() => window.print()}>
            <FileText size={18} />
            Export Report
          </button>
        </div>
      </div>

      <div className="admin-metrics-grid">
        {metrics.map((m, i) => (
          <div key={i} className="admin-card admin-metric-card">
            <div className="metric-icon-box" style={{ backgroundColor: `${m.color}15`, color: m.color }}>
              <m.icon size={24} />
            </div>
            <div className="metric-info">
              <h4>{m.label}</h4>
              <div className="metric-value">{m.value}</div>
              <div className={`metric-trend ${m.trendUp ? 'text-success' : 'text-danger'}`}>
                {m.trendUp ? <ArrowUpRight size={14} /> : <ArrowDownRight size={14} />}
                {m.trend} <span style={{ color: '#94a3b8', fontWeight: 500, marginLeft: '4px' }}>vs last month</span>
              </div>
            </div>
          </div>
        ))}
      </div>

      <div className="admin-dashboard-grid">
        <div className="admin-card">
          <div className="admin-card-header">
            <div>
              <h3>Search Activity</h3>
              <p style={{ fontSize: '0.85rem', color: '#64748b', margin: '4px 0 0' }}>Daily search volume across all regions.</p>
            </div>
            <div className="badge-success admin-badge">
              <TrendingUp size={14} />
              +18.4%
            </div>
          </div>
          <div style={{ height: '300px', width: '100%' }}>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={stats.searchTraffic}>
                <defs>
                  <linearGradient id="colorCount" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="#7047ee" stopOpacity={0.3}/>
                    <stop offset="95%" stopColor="#7047ee" stopOpacity={0}/>
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" vertical={false} stroke="#f1f5f9" />
                <XAxis dataKey="day" axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#94a3b8' }} />
                <YAxis axisLine={false} tickLine={false} tick={{ fontSize: 12, fill: '#94a3b8' }} />
                <Tooltip 
                  contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
                />
                <Area type="monotone" dataKey="count" stroke="#7047ee" strokeWidth={3} fillOpacity={1} fill="url(#colorCount)" />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div className="admin-card">
          <div className="admin-card-header">
            <h3>Recent Platform Activity</h3>
            <button className="btn-outline admin-btn" style={{ padding: '6px 12px', fontSize: '0.75rem' }}>View All</button>
          </div>
          <div className="activity-list">
            {stats.recentActivity && stats.recentActivity.length > 0 ? stats.recentActivity.map((a) => (
              <div key={a.id} style={{ display: 'flex', gap: '16px', padding: '16px 0', borderBottom: '1px solid #f1f5f9' }}>
                <div style={{ 
                  width: '40px', 
                  height: '40px', 
                  borderRadius: '50%', 
                  background: '#f8fafc', 
                  display: 'flex', 
                  alignItems: 'center', 
                  justifyContent: 'center',
                  color: a.type === 'alert' ? '#ef4444' : a.type === 'update' ? '#10b981' : '#3b82f6'
                }}>
                  <Activity size={18} />
                </div>
                <div>
                  <p style={{ margin: 0, fontSize: '0.9rem' }}>
                    <span style={{ fontWeight: 700 }}>{a.user}</span> {a.action}
                  </p>
                  <span style={{ fontSize: '0.8rem', color: '#94a3b8' }}>{a.time}</span>
                </div>
              </div>
            )) : (
              <p style={{ padding: '40px', textAlign: 'center', color: '#94a3b8' }}>No recent activity recorded.</p>
            )}
          </div>
        </div>
      </div>

      <div className="admin-card" style={{ marginTop: '24px' }}>
        <div className="admin-card-header">
          <h3>Top Consulted Medications</h3>
        </div>
        <div style={{ height: '300px', width: '100%' }}>
          <ResponsiveContainer width="100%" height="100%">
            <BarChart data={stats.topDrugs} layout="vertical" margin={{ left: 40, right: 40 }}>
              <XAxis type="number" hide />
              <YAxis dataKey="name" type="category" axisLine={false} tickLine={false} tick={{ fontSize: 12, fontWeight: 600 }} />
              <Tooltip 
                cursor={{ fill: '#f8fafc' }}
                contentStyle={{ borderRadius: '12px', border: 'none', boxShadow: '0 10px 15px -3px rgb(0 0 0 / 0.1)' }}
              />
              <Bar dataKey="count" radius={[0, 4, 4, 0]} barSize={20}>
                {stats.topDrugs.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={index === 0 ? '#7047ee' : '#e2e8f0'} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
};

export default Dashboard;
