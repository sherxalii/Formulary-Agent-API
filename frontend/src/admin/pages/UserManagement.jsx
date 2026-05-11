import React, { useState, useEffect } from 'react';
import { 
  Users, 
  UserPlus, 
  Hourglass, 
  Ban, 
  Search,
  Filter,
  MoreVertical,
  Mail,
  ShieldCheck,
  ChevronDown,
  AlertCircle
} from 'lucide-react';
import { apiRequest } from '../../utils/auth';

const UserManagement = () => {
  const [users, setUsers] = useState([]);
  const [stats, setStats] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchTerm, setSearchTerm] = useState('');
  const [roleFilter, setRoleFilter] = useState('All');

  useEffect(() => {
    const fetchData = async () => {
      const res = await apiRequest('GET', '/admin/users');
      if (res.success) {
        setUsers(res.users);
        setStats(res.stats);
      } else {
        setError('Unable to load user directory. Please check your administrative permissions.');
      }
      setLoading(false);
    };
    fetchData();
  }, []);

  const filteredUsers = users.filter(user => {
    const matchesSearch = user.name.toLowerCase().includes(searchTerm.toLowerCase()) || 
                         user.email.toLowerCase().includes(searchTerm.toLowerCase()) ||
                         (user.specialty && user.specialty.toLowerCase().includes(searchTerm.toLowerCase()));
    const matchesRole = roleFilter === 'All' || user.role === roleFilter;
    return matchesSearch && matchesRole;
  });

  if (loading) return (
    <div className="admin-loading-container">
      <div className="admin-loading-spinner"></div>
      <p>Initializing secure user directory...</p>
    </div>
  );

  if (error) return (
    <div className="admin-error-card">
      <AlertCircle size={48} className="text-danger" />
      <h3>Access Error</h3>
      <p>{error}</p>
      <button className="admin-btn btn-primary" onClick={() => window.location.reload()}>Retry</button>
    </div>
  );

  const statCards = [
    { label: 'Total Members', value: stats?.total ?? 0, icon: Users, color: '#7047ee' },
    { label: 'Active Licenses', value: stats?.active ?? 0, icon: ShieldCheck, color: '#10b981' },
    { label: 'Pending Verification', value: stats?.pending ?? 0, icon: Hourglass, color: '#f59e0b' },
    { label: 'Access Suspended', value: stats?.suspended ?? 0, icon: Ban, color: '#ef4444' },
  ];

  return (
    <div className="animate-fade-in">
      <div className="admin-page-header">
        <div className="header-title">
          <h1>User Directory</h1>
          <p>Verified medical professionals and system administrators.</p>
        </div>
        <button className="admin-btn btn-primary">
          <UserPlus size={18} />
          Add Professional
        </button>
      </div>

      <div className="admin-metrics-grid">
        {statCards.map((card, idx) => (
          <div key={idx} className="admin-card admin-metric-card">
            <div className="metric-icon-box" style={{ backgroundColor: `${card.color}15`, color: card.color }}>
              <card.icon size={22} />
            </div>
            <div className="metric-info">
              <h4>{card.label}</h4>
              <div className="metric-value">{card.value}</div>
            </div>
          </div>
        ))}
      </div>

      <div className="admin-card" style={{ padding: '0' }}>
        <div style={{ padding: '24px', borderBottom: '1px solid var(--admin-divider)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '16px' }}>
          <div className="admin-search-wrapper" style={{ width: '350px' }}>
            <Search size={18} className="search-icon" />
            <input 
              type="text" 
              placeholder="Search by name, email, or specialty..." 
              className="admin-search-input"
              value={searchTerm}
              onChange={(e) => setSearchTerm(e.target.value)}
            />
          </div>
          <div style={{ display: 'flex', gap: '12px' }}>
            <div className="admin-search-wrapper" style={{ width: '160px' }}>
              <select 
                className="admin-search-input" 
                style={{ paddingLeft: '16px', appearance: 'none', cursor: 'pointer' }}
                value={roleFilter}
                onChange={(e) => setRoleFilter(e.target.value)}
              >
                <option value="All">All Roles</option>
                <option value="Admin">Administrators</option>
                <option value="Doctor">Doctors</option>
                <option value="Pharmacist">Pharmacists</option>
                <option value="User">Regular Users</option>
              </select>
              <ChevronDown size={16} style={{ position: 'absolute', right: '16px', top: '50%', transform: 'translateY(-50%)', pointerEvents: 'none', color: 'var(--admin-text-muted)' }} />
            </div>
            <button className="admin-btn btn-outline">
              <Filter size={18} />
              Filters
            </button>
          </div>
        </div>

        <div className="admin-table-container">
          <table className="admin-table">
            <thead>
              <tr>
                <th>Professional</th>
                <th className="hide-on-mobile">Role & Specialty</th>
                <th className="hide-on-mobile">Registration Date</th>
                <th>Status</th>
                <th style={{ textAlign: 'right' }}>Actions</th>
              </tr>
            </thead>
            <tbody>
              {filteredUsers.length > 0 ? filteredUsers.map((user) => (
                <tr key={user.id}>
                  <td>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <div className="admin-avatar" style={{ 
                        background: `linear-gradient(135deg, ${user.color}, ${user.color}dd)`,
                        color: 'white'
                      }}>
                        {user.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()}
                      </div>
                      <div>
                        <div style={{ fontWeight: 700, fontSize: '0.95rem', color: 'var(--admin-text-primary)' }}>{user.name}</div>
                        <div style={{ fontSize: '0.8rem', color: 'var(--admin-text-muted)', display: 'flex', alignItems: 'center', gap: '6px', marginTop: '2px' }}>
                          <Mail size={12} /> {user.email}
                        </div>
                      </div>
                    </div>
                  </td>
                  <td className="hide-on-mobile">
                    <div style={{ fontWeight: 600, color: 'var(--admin-text-primary)' }}>{user.role}</div>
                    <div style={{ fontSize: '0.75rem', color: 'var(--admin-text-muted)' }}>{user.specialty}</div>
                  </td>
                  <td className="hide-on-mobile" style={{ color: 'var(--admin-text-muted)', fontSize: '0.85rem' }}>{user.joined}</td>
                  <td>
                    <span className={`admin-badge ${
                      user.status === 'Active' ? 'badge-success' : 
                      user.status === 'Pending' ? 'badge-warning' : 'badge-danger'
                    }`}>
                      {user.status}
                    </span>
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <div style={{ display: 'flex', justifyContent: 'flex-end', gap: '8px' }}>
                      <button className="admin-btn btn-outline" style={{ padding: '6px 14px', fontSize: '0.8rem', height: '32px' }}>Edit</button>
                      <button className="topbar-action-btn" style={{ width: '32px', height: '32px' }}>
                        <MoreVertical size={16} />
                      </button>
                    </div>
                  </td>
                </tr>
              )) : (
                <tr>
                  <td colSpan="5" style={{ textAlign: 'center', padding: '80px 20px' }}>
                    <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '16px', color: 'var(--admin-text-muted)' }}>
                      <Users size={40} style={{ opacity: 0.2 }} />
                      <p style={{ margin: 0, fontSize: '0.95rem' }}>No professionals found matching your search.</p>
                      <button className="admin-btn btn-outline" style={{ fontSize: '0.8rem', padding: '6px 12px' }} onClick={() => {setSearchTerm(''); setRoleFilter('All');}}>Reset Search</button>
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

export default UserManagement;
