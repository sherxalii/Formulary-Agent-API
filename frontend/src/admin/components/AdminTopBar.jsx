import React, { useState, useRef, useEffect } from 'react';
import { Search, Bell, Menu, User, Settings, LogOut, ChevronDown, Globe } from 'lucide-react';
import { getCurrentUser, logoutUser } from '../../utils/auth';
import { useNavigate, Link } from 'react-router-dom';

const AdminTopBar = ({ onToggleSidebar }) => {
  const user = getCurrentUser() || { name: 'Super Admin', email: 'admin@mediformulary.com', role: 'Administrator' };
  const navigate = useNavigate();
  const [isDropdownOpen, setIsDropdownOpen] = useState(false);
  const dropdownRef = useRef(null);

  const handleLogout = () => {
    logoutUser();
    navigate('/signin');
  };

  // Close dropdown when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (dropdownRef.current && !dropdownRef.current.contains(event.target)) {
        setIsDropdownOpen(false);
      }
    };
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const initials = user.name
    ? user.name.split(' ').map(n => n[0]).join('').slice(0, 2).toUpperCase()
    : 'A';

  return (
    <header className="admin-topbar">
      <div className="topbar-left">
        <button className="topbar-action-btn mobile-only" onClick={onToggleSidebar}>
          <Menu size={20} />
        </button>
        <div className="admin-search-wrapper">
          <Search size={18} className="search-icon" />
          <input 
            type="text" 
            placeholder="Search for drugs, users, or logs..." 
            className="admin-search-input"
          />
        </div>
      </div>

      <div className="topbar-right">
        <Link to="/" className="topbar-action-btn" title="Go to User Side">
          <Globe size={20} />
        </Link>
        
        <button className="topbar-action-btn">
          <Bell size={20} />
          <span className="notification-dot"></span>
        </button>
        
        <div className="admin-profile-container" ref={dropdownRef}>
          <div 
            className={`admin-profile-dropdown ${isDropdownOpen ? 'active' : ''}`} 
            onClick={() => setIsDropdownOpen(!isDropdownOpen)}
          >
            <div className="admin-avatar-small">
              {initials}
            </div>
            <div className="admin-user-meta">
              <span className="user-name">{user.name}</span>
              <span className="user-role">{user.role || 'Admin'}</span>
            </div>
            <ChevronDown size={14} className={`dropdown-arrow ${isDropdownOpen ? 'rotate' : ''}`} />
          </div>

          {isDropdownOpen && (
            <div className="admin-profile-menu">
              <div className="menu-header">
                <strong>{user.name}</strong>
                <span>{user.email}</span>
              </div>
              <div className="menu-divider"></div>
              <button onClick={() => { navigate('/admin/settings'); setIsDropdownOpen(false); }} className="menu-item">
                <Settings size={16} />
                <span>Admin Settings</span>
              </button>
              <Link to="/" className="menu-item" onClick={() => setIsDropdownOpen(false)}>
                <Globe size={16} />
                <span>Main Website</span>
              </Link>
              <div className="menu-divider"></div>
              <button onClick={handleLogout} className="menu-item text-danger">
                <LogOut size={16} />
                <span>Logout</span>
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
};

export default AdminTopBar;
