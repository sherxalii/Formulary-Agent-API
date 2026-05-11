import React, { useEffect } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { loginUser } from '../utils/auth';

const AuthCallback = () => {
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    const params = new URLSearchParams(location.search);
    const token = params.get('token');
    const userJson = params.get('user');

    if (token && userJson) {
      try {
        const user = JSON.parse(decodeURIComponent(userJson));
        loginUser(user, token);
        navigate('/');
      } catch (e) {
        console.error('Error parsing OAuth user data:', e);
        navigate('/signin?error=Failed to process user data');
      }
    } else {
      navigate('/signin?error=OAuth callback failed');
    }
  }, [location, navigate]);

  return (
    <div style={{ 
      height: '100vh', 
      display: 'flex', 
      alignItems: 'center', 
      justifyContent: 'center',
      background: '#f8fafc',
      color: '#1e293b',
      fontFamily: 'Inter, sans-serif'
    }}>
      <div style={{ textAlign: 'center' }}>
        <div style={{ 
          width: '40px', 
          height: '40px', 
          border: '3px solid #e2e8f0', 
          borderTopColor: '#3b82f6', 
          borderRadius: '50%', 
          animation: 'spin 1s linear infinite',
          margin: '0 auto 16px'
        }} />
        <h3>Completing login...</h3>
        <p>Please wait a moment.</p>
      </div>
      <style>{`
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </div>
  );
};

export default AuthCallback;
