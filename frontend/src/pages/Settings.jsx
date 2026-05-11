import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { getCurrentUser, isAuthenticated, updateUser, changePasswordApi } from '../utils/auth';

const icons = {
  settings: (
    <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <circle cx="12" cy="12" r="3" />
      <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83-2.83l.06-.06A1.65 1.65 0 0 0 4.68 15a1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 2.83-2.83l.06.06A1.65 1.65 0 0 0 9 4.68a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 2.83l-.06.06A1.65 1.65 0 0 0 19.4 9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z" />
    </svg>
  ),
  profile: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" /><circle cx="12" cy="7" r="4" />
    </svg>
  ),
  security: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <rect x="3" y="11" width="18" height="11" rx="2" /><path d="M7 11V7a5 5 0 0 1 10 0v4" />
    </svg>
  ),
  preferences: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="12" cy="12" r="3" /><path d="M12 1v4M12 19v4M4.22 4.22l2.83 2.83M16.95 16.95l2.83 2.83M1 12h4M19 12h4M4.22 19.78l2.83-2.83M16.95 7.05l2.83-2.83" />
    </svg>
  ),
  advanced: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M22 12h-4l-3 9L9 3l-3 9H2" />
    </svg>
  ),
  check: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22 4 12 14.01 9 11.01" />
    </svg>
  ),
  error: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <circle cx="12" cy="12" r="10" /><line x1="15" y1="9" x2="9" y2="15" /><line x1="9" y1="9" x2="15" y2="15" />
    </svg>
  ),
  eye: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z" /><circle cx="12" cy="12" r="3" />
    </svg>
  ),
  eyeOff: (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19m-6.72-1.07a3 3 0 1 1-4.24-4.24" />
      <line x1="1" y1="1" x2="23" y2="23" />
    </svg>
  ),
  hipaa: (
    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
    </svg>
  ),
  chevron: (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <polyline points="9 18 15 12 9 6" />
    </svg>
  ),
  privacy: (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
      <path d="M12 8v4" /><path d="M12 16h.01" />
    </svg>
  ),
};

const navItems = [
  { key: 'profile', label: 'Account Profile', icon: icons.profile },
  { key: 'security', label: 'Security Settings', icon: icons.security },
  { key: 'preferences', label: 'Preferences', icon: icons.preferences },
  { key: 'privacy', label: 'Privacy & Cookies', icon: icons.privacy },
  { key: 'advanced', label: 'Advanced', icon: icons.advanced },
];

const PasswordInput = ({ id, name, value, onChange }) => {
  const [show, setShow] = useState(false);
  return (
    <div className="st-pw-wrap">
      <input
        id={id} name={name}
        type={show ? 'text' : 'password'}
        value={value} onChange={onChange}
        placeholder="••••••••" required
      />
      <button type="button" className="st-pw-toggle" onClick={() => setShow(s => !s)}>
        {show ? icons.eyeOff : icons.eye}
      </button>
    </div>
  );
};

const Settings = () => {
  const navigate = useNavigate();
  const [user, setUser] = useState(() => getCurrentUser());
  const [activeTab, setActiveTab] = useState('profile');
  const [status, setStatus] = useState({ msg: '', type: '' });
  const [formData, setFormData] = useState(() => {
    const u = getCurrentUser() || {};
    return {
      name: u.name || '',
      email: u.email || '',
      department: u.department || 'General',
      role: u.role || 'User',
      formulary: u.formulary || 'commercial',
      alerts: u.alerts ?? true,
      theme: u.theme || 'light',
    };
  });
  const [passwordForm, setPasswordForm] = useState({
    current_password: '', new_password: '', confirm_password: '',
  });

  useEffect(() => {
    if (!isAuthenticated()) { navigate('/signin'); return; }
    const u = getCurrentUser();
    if (!u) { navigate('/signin'); return; }
    // No need to setUser here as it's initialized above
  }, [navigate]);

  const showStatus = (msg, type = 'success') => {
    setStatus({ msg, type });
    window.setTimeout(() => setStatus({ msg: '', type: '' }), 3500);
  };

  const handleChange = (e) => {
    const { name, value, type, checked } = e.target;
    const val = type === 'checkbox' ? checked : value;
    const next = { ...formData, [name]: val };
    setFormData(next);
    if (['alerts', 'formulary', 'theme'].includes(name)) {
      const updated = updateUser(next);
      if (updated) setUser(updated);
    }
  };

  const handleThemeChange = (theme) => {
    const next = { ...formData, theme };
    setFormData(next);
    const updated = updateUser(next);
    if (updated) setUser(updated);
    showStatus(`Switched to ${theme === 'light' ? 'Light' : 'Dark'} Mode.`);
  };

  const handleSubmit = (e) => {
    e.preventDefault();
    const updated = updateUser(formData);
    if (updated) { setUser(updated); showStatus('Profile updated successfully.'); }
    else showStatus('Unable to save changes. Please sign in again.', 'error');
  };

  const handlePasswordSubmit = async (e) => {
    e.preventDefault();
    if (passwordForm.new_password !== passwordForm.confirm_password) {
      showStatus('New passwords do not match.', 'error'); return;
    }
    const res = await changePasswordApi({
      email: user.email,
      current_password: passwordForm.current_password,
      new_password: passwordForm.new_password,
    });
    if (res.success) {
      setPasswordForm({ current_password: '', new_password: '', confirm_password: '' });
      showStatus('Password updated successfully.');
    } else {
      showStatus(res.error || res.message || 'Unable to update password.', 'error');
    }
  };

  if (!user) return null;

  const initials = user.name
    ? user.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : 'U';

  const renderTab = () => {
    switch (activeTab) {

      /* ── Profile ── */
      case 'profile': return (
        <div className="st-section">
          <div className="st-section-head">
            <h3>Account Profile</h3>
            <p>Update your personal details and role information.</p>
          </div>

          <div className="st-profile-card">
            <div className="st-avatar">{initials}</div>
            <div className="st-profile-meta">
              <div className="st-profile-name">{user.name || 'User'}</div>
              <div className="st-profile-email">{user.email}</div>
              <div className="st-role-badge">{user.role || 'User'}</div>
            </div>
            <button className="st-btn-ghost" type="button">Change Photo</button>
          </div>

          <form className="st-form" onSubmit={handleSubmit}>
            <div className="st-form-grid">
              <div className="st-field">
                <label htmlFor="name">Full Name</label>
                <input id="name" name="name" type="text" value={formData.name} onChange={handleChange} required />
              </div>
              <div className="st-field">
                <label htmlFor="email">Email Address</label>
                <input id="email" name="email" type="email" value={formData.email} onChange={handleChange} required />
              </div>
              <div className="st-field">
                <label htmlFor="department">Department</label>
                <input id="department" name="department" type="text" value={formData.department} onChange={handleChange} />
              </div>
              <div className="st-field">
                <label htmlFor="role">Role <span className="st-field-note">(read-only)</span></label>
                <input id="role" name="role" type="text" value={formData.role} disabled />
              </div>
            </div>
            <div className="st-form-footer">
              <button type="submit" className="st-btn-primary">Save Changes</button>
            </div>
          </form>
        </div>
      );

      /* ── Security ── */
      case 'security': return (
        <div className="st-section">
          <div className="st-section-head">
            <h3>Security Settings</h3>
            <p>Manage your password and account access controls.</p>
          </div>

          <div className="st-info-banner">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <circle cx="12" cy="12" r="10" /><line x1="12" y1="8" x2="12" y2="12" /><line x1="12" y1="16" x2="12.01" y2="16" />
            </svg>
            Use a minimum of 8 characters with a mix of letters, numbers, and symbols.
          </div>

          <form className="st-form" onSubmit={handlePasswordSubmit}>
            <div className="st-section-sub">Change Password</div>
            <div className="st-form-grid st-form-grid--1col">
              <div className="st-field">
                <label htmlFor="current_password">Current Password</label>
                <PasswordInput id="current_password" name="current_password"
                  value={passwordForm.current_password}
                  onChange={e => setPasswordForm({ ...passwordForm, current_password: e.target.value })} />
              </div>
            </div>
            <div className="st-form-grid">
              <div className="st-field">
                <label htmlFor="new_password">New Password</label>
                <PasswordInput id="new_password" name="new_password"
                  value={passwordForm.new_password}
                  onChange={e => setPasswordForm({ ...passwordForm, new_password: e.target.value })} />
              </div>
              <div className="st-field">
                <label htmlFor="confirm_password">Confirm Password</label>
                <PasswordInput id="confirm_password" name="confirm_password"
                  value={passwordForm.confirm_password}
                  onChange={e => setPasswordForm({ ...passwordForm, confirm_password: e.target.value })} />
              </div>
            </div>
            <div className="st-form-footer">
              <button type="submit" className="st-btn-primary">Update Password</button>
            </div>
          </form>

          <div className="st-divider" />
          <div className="st-section-sub">Access Controls</div>

          <div className="st-security-row">
            <div className="st-security-icon st-security-icon--green">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              </svg>
            </div>
            <div className="st-security-body">
              <div className="st-security-title">Two-Factor Authentication</div>
              <div className="st-security-desc">Enabled via Authenticator App</div>
            </div>
            <span className="st-status-chip st-status-chip--green">Active</span>
            <button className="st-btn-ghost" type="button"
              onClick={() => showStatus('Two-factor settings opened.')}>Manage</button>
          </div>

          <div className="st-security-row st-security-row--danger">
            <div className="st-security-icon st-security-icon--red">
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" />
                <path d="M10 11v6M14 11v6M9 6V4h6v2" />
              </svg>
            </div>
            <div className="st-security-body">
              <div className="st-security-title st-text-danger">Delete Account</div>
              <div className="st-security-desc">Permanently remove your account and all associated data.</div>
            </div>
            <button className="st-btn-danger" type="button"
              onClick={() => showStatus('Account deletion request submitted.', 'error')}>Terminate</button>
          </div>
        </div>
      );

      /* ── Preferences ── */
      case 'preferences': return (
        <div className="st-section">
          <div className="st-section-head">
            <h3>Preferences</h3>
            <p>Manage how MediFormulary looks and behaves for you.</p>
          </div>

          <div className="st-pref-list">
            <div className="st-pref-row">
              <div className="st-pref-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
                  <path d="M13.73 21a2 2 0 0 1-3.46 0" />
                </svg>
              </div>
              <div className="st-pref-body">
                <div className="st-pref-title">Email Notifications</div>
                <div className="st-pref-desc">Receive alerts for important drug formulary updates</div>
              </div>
              <label className="st-toggle">
                <input type="checkbox" id="alerts" name="alerts" checked={formData.alerts} onChange={handleChange} />
                <span className="st-toggle-track"><span className="st-toggle-thumb" /></span>
              </label>
            </div>

            <div className="st-pref-row">
              <div className="st-pref-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M3 9l9-7 9 7v11a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2z" />
                  <polyline points="9 22 9 12 15 12 15 22" />
                </svg>
              </div>
              <div className="st-pref-body">
                <div className="st-pref-title">Default Insurance Plan</div>
                <div className="st-pref-desc">Automatically selected when starting a new drug search</div>
              </div>
              <div className="st-select-wrap">
                <select id="formulary" name="formulary" value={formData.formulary} onChange={handleChange}>
                  <option value="commercial">Commercial</option>
                  <option value="medicaid">Medicaid</option>
                  <option value="medicare">Medicare</option>
                  <option value="other">Other</option>
                </select>
              </div>
            </div>

            <div className="st-pref-row">
              <div className="st-pref-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <circle cx="12" cy="12" r="5" />
                  <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                </svg>
              </div>
              <div className="st-pref-body">
                <div className="st-pref-title">Appearance Theme</div>
                <div className="st-pref-desc">Choose between light and dark system themes</div>
              </div>
              <div className="st-theme-btns">
                <button type="button"
                  className={`st-theme-btn ${formData.theme === 'light' ? 'active' : ''}`}
                  onClick={() => handleThemeChange('light')}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <circle cx="12" cy="12" r="5" />
                    <path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42" />
                  </svg>
                  Light
                </button>
                <button type="button"
                  className={`st-theme-btn ${formData.theme === 'dark' ? 'active' : ''}`}
                  onClick={() => handleThemeChange('dark')}>
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                    <path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z" />
                  </svg>
                  Dark
                </button>
              </div>
            </div>
          </div>
        </div>
      );

      /* ── Privacy & Cookies ── */
      case 'privacy': return (
        <div className="st-section">
          <div className="st-section-head">
            <h3>Privacy & Cookies</h3>
            <p>Manage your data privacy settings and cookie preferences.</p>
          </div>

          <div className="st-pref-list">
            <div className="st-pref-row">
              <div className="st-pref-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                </svg>
              </div>
              <div className="st-pref-body">
                <div className="st-pref-title">Cookie Consent</div>
                <div className="st-pref-desc">
                  {localStorage.getItem('cookieConsent') 
                    ? `Status: ${localStorage.getItem('cookieConsent') === 'accepted' ? 'Accepted' : 'Declined'}` 
                    : 'Status: Not Set'}
                </div>
              </div>
              <button 
                className="st-btn-ghost" 
                type="button"
                onClick={() => {
                  localStorage.removeItem('cookieConsent');
                  window.location.reload();
                }}
              >
                Reset Preferences
              </button>
            </div>

            <div className="st-pref-row">
              <div className="st-pref-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z" />
                </svg>
              </div>
              <div className="st-pref-body">
                <div className="st-pref-title">Data Privacy Policy</div>
                <div className="st-pref-desc">Read our full privacy and cookies policy</div>
              </div>
              <button 
                className="st-btn-ghost" 
                type="button"
                onClick={() => navigate('/privacy')}
              >
                View Policy
              </button>
            </div>
          </div>
        </div>
      );

      /* ── Advanced ── */
      case 'advanced': return (
        <div className="st-section">
          <div className="st-section-head">
            <h3>Advanced Overview</h3>
            <p>Monitor system health and manage data storage.</p>
          </div>

          <div className="st-section-sub">System Status</div>
          <div className="st-status-grid">
            {[
              { label: 'Backend API', value: 'Operational', type: 'success' },
              { label: 'Database Sync', value: 'Active', type: 'success' },
              { label: 'Current Node', value: 'Med-Alpha-01', type: 'neutral' },
            ].map(({ label, value, type }) => (
              <div key={label} className="st-status-card">
                <div className={`st-status-dot st-status-dot--${type}`} />
                <div>
                  <span className="st-status-label">{label}</span>
                  <div className={`st-status-val st-status-val--${type}`}>{value}</div>
                </div>
              </div>
            ))}
          </div>

          <div className="st-divider" />
          <div className="st-section-sub">Data Management</div>

          <div className="st-action-list">
            <div className="st-action-row">
              <div className="st-action-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <polyline points="3 6 5 6 21 6" /><path d="M19 6l-1 14H6L5 6" />
                  <path d="M10 11v6M14 11v6M9 6V4h6v2" />
                </svg>
              </div>
              <div className="st-action-body">
                <div className="st-action-title">Search History Cache</div>
                <div className="st-action-desc">32.5 MB stored locally</div>
              </div>
              <button className="st-btn-ghost" type="button"
                onClick={() => showStatus('Search history cache purged successfully.')}>Purge Cache</button>
            </div>

            <div className="st-action-row">
              <div className="st-action-icon">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                  <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
                  <polyline points="14 2 14 8 20 8" />
                  <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
                </svg>
              </div>
              <div className="st-action-body">
                <div className="st-action-title">Application Logs</div>
                <div className="st-action-desc">View diagnostic logs for system incidents</div>
              </div>
              <button className="st-btn-ghost" type="button"
                onClick={() => showStatus('Application logs exported successfully.')}>Export Logs</button>
            </div>
          </div>
        </div>
      );

      default: return null;
    }
  };

  return (
    <div className="st-root">

      {/* ── Page Header ── */}
      <div className="st-page-header">
        <div className="st-page-header-inner">
          <div className="st-page-icon">{icons.settings}</div>
          <div>
            <h2 className="st-page-title">Account Settings</h2>
            <p className="st-page-desc">Manage your profile, security, and system preferences.</p>
          </div>
        </div>
        <div className="st-header-user">
          <div className="st-header-avatar">{initials}</div>
          <div>
            <div className="st-header-name">{user.name}</div>
            <div className="st-header-role">{user.role || 'User'}</div>
          </div>
        </div>
      </div>

      {/* ── Layout ── */}
      <div className="st-layout">

        {/* Sidebar */}
        <aside className="st-sidebar">
          <nav className="st-nav">
            {navItems.map(({ key, label, icon }) => (
              <button
                key={key}
                className={`st-nav-btn ${activeTab === key ? 'active' : ''}`}
                onClick={() => setActiveTab(key)}
              >
                <span className="st-nav-icon">{icon}</span>
                <span className="st-nav-label">{label}</span>
                <span className="st-nav-chevron">{icons.chevron}</span>
              </button>
            ))}
          </nav>

          <div className="st-sidebar-card">
            <div className="st-sidebar-card-icon">{icons.hipaa}</div>
            <div className="st-sidebar-card-title">HIPAA Compliant</div>
            <div className="st-sidebar-card-desc">
              Your data is encrypted and stored in compliance with all applicable healthcare regulations.
            </div>
          </div>
        </aside>

        {/* Content */}
        <div className="st-content">
          {renderTab()}
          {status.msg && (
            <div className={`st-toast st-toast--${status.type}`}>
              {status.type === 'success' ? icons.check : icons.error}
              {status.msg}
            </div>
          )}
        </div>

      </div>
    </div>
  );
};

export default Settings;