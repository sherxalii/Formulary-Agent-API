import React, { useState } from 'react';
import { NavLink, Outlet, useNavigate } from 'react-router-dom';
import {
  LayoutDashboard,
  BarChart3,
  Users,
  Database,
  FileText,
  Star,
  ShieldAlert,
  Activity,
  Settings,
  LogOut,
  Search,
  ChevronRight,
  Globe
} from 'lucide-react';
import { getCurrentUser, logoutUser } from '../utils/auth';
import AdminTopBar from './components/AdminTopBar';
import './Admin.css';

const AdminLayout = () => {
  const [isSidebarOpen, setIsSidebarOpen] = useState(true);
  const user = getCurrentUser() || { name: 'Super Admin', email: 'admin@mediformulary.com' };
  const navigate = useNavigate();

  const handleLogout = () => {
    logoutUser();
    navigate('/signin');
  };

  const navGroups = [
    {
      title: 'Platform',
      items: [
        { label: 'Dashboard', path: '/admin', icon: LayoutDashboard, end: true },
        { label: 'Analytics', path: '/admin/analytics', icon: BarChart3 },
      ]
    },
    {
      title: 'Management',
      items: [
        { label: 'User management', path: '/admin/users', icon: Users },
        { label: 'Drug database', path: '/admin/drugs', icon: Database },
        { label: 'Documents & PDFs', path: '/admin/documents', icon: FileText },
        { label: 'Formulary plans', path: '/admin/plans', icon: Star },
      ]
    },
    {
      title: 'Intelligence',
      items: [
        { label: 'Model performance', path: '/admin/models', icon: Activity },
        { label: 'Drug alerts', path: '/admin/alerts', icon: ShieldAlert },
      ]
    },
    {
      title: 'System',
      items: [
        { label: 'Audit logs', path: '/admin/audit', icon: Activity },
      ]
    }
  ];

  return (
    <div className="admin-wrapper">
      <aside className={`admin-sidebar ${isSidebarOpen ? 'open' : 'closed'}`}>
        <div className="admin-sidebar-header">
          <div className="admin-logo-box">
            <Search size={22} strokeWidth={3} />
          </div>
          <div className="admin-brand-info">
            <h2>MediFormulary</h2>
            <span>Admin Control</span>
          </div>
        </div>

        <nav className="admin-nav">
          {navGroups.map((group, gIdx) => (
            <div key={gIdx} className="admin-nav-section">
              <h3 className="admin-nav-title">{group.title}</h3>
              {group.items.map((item, iIdx) => (
                <NavLink
                  key={iIdx}
                  to={item.path}
                  className={({ isActive }) => `admin-nav-item ${isActive ? 'active' : ''}`}
                  end={item.end}
                >
                  <item.icon size={18} />
                  <span>{item.label}</span>
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        <div className="admin-sidebar-footer">
          <button onClick={handleLogout} className="admin-nav-item" style={{ width: '100%', border: 'none', background: 'transparent', cursor: 'pointer' }}>
            <LogOut size={18} />
            <span>Logout</span>
          </button>
        </div>
      </aside>

      <div className="admin-main">
        <AdminTopBar onToggleSidebar={() => setIsSidebarOpen(!isSidebarOpen)} />
        <main className="admin-content">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

export default AdminLayout;
