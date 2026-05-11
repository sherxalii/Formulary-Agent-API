import { BrowserRouter as Router, Routes, Route, Navigate, Outlet } from 'react-router-dom';
import { Toaster } from 'react-hot-toast';
import Header from './components/Header';
import Footer from './components/Footer';
import Home from './pages/Home';
import Search from './pages/Search';
import Formulary from './pages/Formulary';
import About from './pages/About';
import Contact from './pages/Contact';
import SignIn from './pages/SignIn';
import Settings from './pages/Settings';
import Bookmarks from './pages/Bookmarks';
import AuthCallback from './pages/AuthCallback';
import PrivacyPolicy from './pages/PrivacyPolicy';
import TermsOfService from './pages/TermsOfService';
import DDI from './pages/DDI';
import { isAuthenticated, isAdmin } from './utils/auth';
import MediformAI from './components/ClinicalAIAssistant';
import CookieConsent from './components/CookieConsent';

// Admin Imports
import AdminLayout from './admin/AdminLayout';
import Dashboard from './admin/pages/Dashboard';
import DatabaseManagement from './admin/pages/DatabaseManagement';
import UserManagement from './admin/pages/UserManagement';
import DrugDatabase from './admin/pages/DrugDatabase';
import DrugAlerts from './admin/pages/DrugAlerts';
import { Analytics, FormularyPlans, ModelPerformance, AuditLogs, AdminSettings } from './admin/pages/Placeholders';

const PrivateRoute = ({ children }) => {
  return isAuthenticated() ? children : <Navigate to="/signin" replace />;
};

const AdminRoute = ({ children }) => {
  return isAuthenticated() && isAdmin() ? children : <Navigate to="/" replace />;
};

// Layout for public pages to include Header, Footer, and floating components
const PublicLayout = () => (
  <>
    <Header />
    <main>
      <Outlet />
    </main>
    <Footer />
    <MediformAI />
    <CookieConsent />
  </>
);

function App() {
  return (
    <Router>
      <Toaster 
        position="top-center" 
        reverseOrder={false}
        containerStyle={{
          top: 80,
        }}
        toastOptions={{
          className: 'glass-toast',
          duration: 4000,
          style: {
            background: 'rgba(255, 255, 255, 0.7)',
            backdropFilter: 'blur(16px) saturate(180%)',
            WebkitBackdropFilter: 'blur(16px) saturate(180%)',
            border: '1px solid rgba(255, 255, 255, 0.3)',
            borderRadius: '16px',
            boxShadow: '0 8px 32px 0 rgba(31, 38, 135, 0.15)',
            color: '#1a365d',
            padding: '12px 20px',
            fontSize: '15px',
            fontWeight: '600',
            maxWidth: '400px',
          },
          success: {
            style: {
              background: 'rgba(255, 255, 255, 0.7)',
              border: '1px solid rgba(22, 160, 133, 0.4)',
              color: '#0f6e56',
            },
            iconTheme: {
              primary: '#16a085',
              secondary: '#fff',
            },
          },
          error: {
            style: {
              background: 'rgba(255, 255, 255, 0.7)',
              border: '1px solid rgba(229, 62, 62, 0.4)',
              color: '#c53030',
            },
            iconTheme: {
              primary: '#e53e3e',
              secondary: '#fff',
            },
          },
        }}
      />
      <Routes>
        {/* Admin Routes */}
        <Route path="/admin" element={<AdminRoute><AdminLayout /></AdminRoute>}>
          <Route index element={<Dashboard />} />
          <Route path="analytics" element={<Analytics />} />
          <Route path="users" element={<UserManagement />} />
          <Route path="drugs" element={<DrugDatabase />} />
          <Route path="documents" element={<DatabaseManagement />} />
          <Route path="database-management" element={<Navigate to="/admin/documents" replace />} />
          <Route path="plans" element={<FormularyPlans />} />
          <Route path="models" element={<ModelPerformance />} />
          <Route path="alerts" element={<DrugAlerts />} />
          <Route path="audit" element={<AuditLogs />} />
          <Route path="settings" element={<AdminSettings />} />
        </Route>

        {/* Public Routes */}
        <Route path="/database" element={<Navigate to="/admin/documents" replace />} />
        <Route path="/drug-database" element={<Navigate to="/admin/drugs" replace />} />
        <Route element={<PublicLayout />}>
          <Route path="/" element={<Home />} />
          <Route path="/search" element={<Search />} />
          <Route path="/formulary" element={<Formulary />} />
          <Route path="/about" element={<About />} />
          <Route path="/contact" element={<Contact />} />
          <Route path="/signin" element={<SignIn />} />
          <Route path="/auth/callback" element={<AuthCallback />} />
          <Route path="/settings" element={<PrivateRoute><Settings /></PrivateRoute>} />
          <Route path="/bookmarks" element={<Bookmarks />} />
          <Route path="/ddi" element={<DDI />} />
          <Route path="/privacy" element={<PrivacyPolicy />} />
          <Route path="/terms" element={<TermsOfService />} />
        </Route>
      </Routes>
    </Router>
  );
}

export default App;
