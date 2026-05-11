import React, { useEffect, useState, useRef } from 'react';
import { Link, useLocation, useNavigate } from 'react-router-dom';
import { getCurrentUser, isAuthenticated, logoutUser, isAdmin } from '../utils/auth';

const Header = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [user, setUser] = useState(getCurrentUser());
  const [showProfileMenu, setShowProfileMenu] = useState(false);
  const profileMenuRef = useRef(null);

  const isActive = (path) => {
    return location.pathname === path ? 'active' : '';
  };

  const [bookmarksCount, setBookmarksCount] = useState(0);

  const getBookmarksCount = () => {
    try {
      return JSON.parse(localStorage.getItem('mediformulary_bookmarks') || '[]').length;
    } catch {
      return 0;
    }
  };

  useEffect(() => {
    const handleAuthChange = () => setUser(getCurrentUser());
    const handleBookmarkChange = () => setBookmarksCount(getBookmarksCount());

    setBookmarksCount(getBookmarksCount());

    window.addEventListener('authChange', handleAuthChange);
    window.addEventListener('bookmarksChange', handleBookmarkChange);

    return () => {
      window.removeEventListener('authChange', handleAuthChange);
      window.removeEventListener('bookmarksChange', handleBookmarkChange);
    };
  }, []);

  // Close profile menu when clicking outside
  useEffect(() => {
    const handleClickOutside = (event) => {
      if (profileMenuRef.current && !profileMenuRef.current.contains(event.target)) {
        setShowProfileMenu(false);
      }
    };

    document.addEventListener('mousedown', handleClickOutside);
    return () => {
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, []);

  const handleLogout = () => {
    logoutUser();
    setUser(null);
    setShowProfileMenu(false);
    navigate('/signin');
  };

  return (
    <header>
      <nav className="navbar">
        <Link to="/" className="logo">
          <svg className="logo-icon" viewBox="0 0 24 24">
            <path d="M12 2C6.48 2 2 6.48 2 12s4.48 10 10 10 10-4.48 10-10S17.52 2 12 2zm-1 17.93c-3.95-.49-7-3.85-7-7.93 0-.62.08-1.21.21-1.79L9 15v1c0 1.1.9 2 2 2v1.93zm6.9-2.54c-.26-.81-1-1.39-1.9-1.39h-1v-3c0-.55-.45-1-1-1H8v-2h2c.55 0 1-.45 1-1V7h2c1.1 0 2-.9 2-2v-.41c2.93 1.19 5 4.06 5 7.41 0 2.08-.8 3.97-2.1 5.39z" />
          </svg>
          <span className="logo-text">MediFormulary</span>
        </Link>

        <div className="nav-pill-wrapper">
          <ul className="nav-links">
            <li><Link to="/" className={isActive('/')}>Home</Link></li>
            <li><Link to="/search" className={isActive('/search')}>Search</Link></li>
            <li><Link to="/formulary" className={isActive('/formulary')}>Formulary</Link></li>
            <li><Link to="/ddi" className={isActive('/ddi')}>DDI </Link></li>
            <li><Link to="/about" className={isActive('/about')}>About</Link></li>
            <li><Link to="/contact" className={isActive('/contact')}>Contact</Link></li>
          </ul>
        </div>

        <div className="nav-actions">
          <button className="icon-btn" title="Notifications">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"></path>
              <path d="M13.73 21a2 2 0 0 1-3.46 0"></path>
            </svg>
          </button>
          <Link to="/bookmarks" className="icon-btn" title="Bookmarks">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"></path>
            </svg>
            {bookmarksCount > 0 && <span className="badge">{bookmarksCount}</span>}
          </Link>
          {user ? (
            <div className="profile-section" ref={profileMenuRef}>
              <button
                className="nav-avatar"
                onClick={() => setShowProfileMenu(!showProfileMenu)}
                title={user.name || 'Profile'}
              >
                {user.name ? user.name.charAt(0).toUpperCase() : 'U'}
              </button>

              {showProfileMenu && (
                <div className="profile-dropdown">
                  <div className="profile-info">
                    <div className="profile-name">{user.name}</div>
                    <div className="profile-email">{user.email}</div>
                    <div className="profile-role">{user.role}</div>
                  </div>
                  <div className="profile-menu">
                    <Link to="/settings" onClick={() => setShowProfileMenu(false)}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <circle cx="12" cy="12" r="3"></circle>
                        <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1 1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
                      </svg>
                      Settings
                    </Link>
                    {isAdmin() && (
                      <Link to="/admin" onClick={() => setShowProfileMenu(false)}>
                        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                          <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
                          <line x1="9" y1="9" x2="15" y2="15"></line>
                          <line x1="15" y1="9" x2="9" y2="15"></line>
                        </svg>
                        Admin Dashboard
                      </Link>
                    )}
                    <button onClick={handleLogout}>
                      <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                        <path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path>
                        <polyline points="16 17 21 12 16 7"></polyline>
                        <line x1="21" y1="12" x2="9" y2="12"></line>
                      </svg>
                      Logout
                    </button>
                  </div>
                </div>
              )}
            </div>
          ) : (
            <Link
              to="/signin"
              className="btn-login"
              style={{ textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '8px' }}
            >
              <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                <circle cx="12" cy="7" r="4"></circle>
              </svg>
              Login
            </Link>
          )}
        </div>
      </nav>

      <style>{`
        .profile-section {
          position: relative;
        }

        .profile-dropdown {
          position: absolute;
          top: 100%;
          right: 0;
          background: white;
          border-radius: 8px;
          box-shadow: 0 4px 12px rgba(0, 0, 0, 0.15);
          border: 1px solid #e5e7eb;
          min-width: 200px;
          z-index: 1000;
          margin-top: 8px;
        }

        .profile-info {
          padding: 16px;
          border-bottom: 1px solid #e5e7eb;
        }

        .profile-name {
          font-weight: 600;
          color: #1f2937;
          margin-bottom: 4px;
        }

        .profile-email {
          font-size: 14px;
          color: #6b7280;
          margin-bottom: 2px;
        }

        .profile-role {
          font-size: 12px;
          color: #9ca3af;
          background: #f3f4f6;
          padding: 2px 6px;
          border-radius: 4px;
          display: inline-block;
        }

        .profile-menu {
          padding: 8px 0;
        }

        .profile-menu a,
        .profile-menu button {
          display: flex;
          align-items: center;
          gap: 8px;
          width: 100%;
          padding: 8px 16px;
          border: none;
          background: none;
          text-align: left;
          cursor: pointer;
          color: #374151;
          text-decoration: none;
          font-size: 14px;
          transition: background-color 0.2s;
        }

        .profile-menu a:hover,
        .profile-menu button:hover {
          background: #f9fafb;
        }

        .profile-menu button {
          color: #dc2626;
        }

        .profile-menu button:hover {
          background: #fef2f2;
        }
      `}</style>
    </header>
  );
};

export default Header;
