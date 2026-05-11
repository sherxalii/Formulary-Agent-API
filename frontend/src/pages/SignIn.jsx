import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { loginUser, registerUserApi, loginUserApi } from '../utils/auth';

const SignIn = () => {
  const navigate = useNavigate();
  const [isRightPanelActive, setIsRightPanelActive] = useState(false);
  const [statusMessage, setStatusMessage] = useState('');

  const [signInData, setSignInData] = useState({ email: '', password: '' });
  const [signUpData, setSignUpData] = useState({ name: '', email: '', password: '', role: 'User' });

  const handleSignIn = async (e) => {
    e.preventDefault();

    const response = await loginUserApi(signInData);
    if (response.success && response.access_token) {
      loginUser(response.user, response.access_token);
      navigate('/');
      return;
    }

    setStatusMessage(response.error || response.message || 'Login failed. Please check your credentials.');
  };

  const handleGoogleLogin = () => {
    window.location.href = 'http://localhost:8000/api/auth/login/google';
  };

  const handleSignUp = async (e) => {
    e.preventDefault();

    const response = await registerUserApi(signUpData);
    if (response.success && response.access_token) {
      loginUser(response.user, response.access_token);
      navigate('/');
      return;
    }

    setStatusMessage(response.error || response.message || 'Registration failed. Please try again.');
  };
  return (
    <div className="modern-auth-body">
      <div className={`modern-auth-container${isRightPanelActive ? ' right-panel-active' : ''}`}>

        {/* Sign In Form */}
        <div className="modern-form-container sign-in-container">
          <form onSubmit={handleSignIn}>
            <h2>Sign In</h2>
            <div className="social-container">
              <button 
                type="button"
                onClick={handleGoogleLogin}
                className="google-login-button"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" style={{ marginRight: '10px' }}>
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-1 .67-2.28 1.07-3.71 1.07-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.11c-.22-.66-.35-1.36-.35-2.11s.13-1.45.35-2.11V7.05H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.95l3.66-2.84z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.05l3.66 2.84c.87-2.6 3.3-4.51 6.16-4.51z" fill="#EA4335"/>
                </svg>
                Sign in with Google
              </button>
            </div>
            <span>or use your account</span>
            {statusMessage ? (
              <div style={{ color: '#e53e3e', margin: '8px 0', fontSize: '14px', textAlign: 'center' }}>
                {statusMessage}
              </div>
            ) : null}
            <input
              type="email"
              placeholder="Email"
              required
              value={signInData.email}
              onChange={(e) => setSignInData({ ...signInData, email: e.target.value })}
            />
            <input
              type="password"
              placeholder="Password"
              required
              value={signInData.password}
              onChange={(e) => setSignInData({ ...signInData, password: e.target.value })}
            />
            <button type="submit" className="modern-btn">Sign In</button>
            <button
              type="button"
              className="mobile-toggle"
              onClick={() => setIsRightPanelActive(true)}
            >
              Don't have an account? Sign Up
            </button>
          </form>
        </div>

        {/* Sign Up Form */}
        <div className="modern-form-container sign-up-container">
          <form onSubmit={handleSignUp}>
            <h2>Create Account</h2>
            <div className="social-container">
              <button 
                type="button"
                onClick={handleGoogleLogin}
                className="google-login-button"
              >
                <svg width="18" height="18" viewBox="0 0 24 24" style={{ marginRight: '10px' }}>
                  <path d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92c-.26 1.37-1.04 2.53-2.21 3.31v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.09z" fill="#4285F4"/>
                  <path d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-1 .67-2.28 1.07-3.71 1.07-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z" fill="#34A853"/>
                  <path d="M5.84 14.11c-.22-.66-.35-1.36-.35-2.11s.13-1.45.35-2.11V7.05H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.95l3.66-2.84z" fill="#FBBC05"/>
                  <path d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.05l3.66 2.84c.87-2.6 3.3-4.51 6.16-4.51z" fill="#EA4335"/>
                </svg>
                Sign up with Google
              </button>
            </div>
            <span>or use your email for registration</span>
            {statusMessage ? (
              <div style={{ color: '#e53e3e', margin: '8px 0', fontSize: '14px', textAlign: 'center' }}>
                {statusMessage}
              </div>
            ) : null}
            <input
              type="text"
              placeholder="Full Name"
              required
              value={signUpData.name}
              onChange={(e) => setSignUpData({ ...signUpData, name: e.target.value })}
            />
            <input
              type="email"
              placeholder="Email"
              required
              value={signUpData.email}
              onChange={(e) => setSignUpData({ ...signUpData, email: e.target.value })}
            />
            <input
              type="password"
              placeholder="Password"
              required
              value={signUpData.password}
              onChange={(e) => setSignUpData({ ...signUpData, password: e.target.value })}
            />
            <div className="auth-select-wrapper">
              <select 
                value={signUpData.role}
                onChange={(e) => setSignUpData({ ...signUpData, role: e.target.value })}
                required
                className="auth-select"
              >
                <option value="" disabled>Select Professional Role</option>
                <option value="Doctor">Medical Doctor</option>
                <option value="Pharmacist">Clinical Pharmacist</option>
                <option value="User">Standard User</option>
              </select>
            </div>
            <button type="submit" className="modern-btn">Sign Up</button>
            <button
              type="button"
              className="mobile-toggle"
              onClick={() => setIsRightPanelActive(false)}
            >
              Already have an account? Sign In
            </button>
          </form>
        </div>

        {/* Overlay */}
        <div className="overlay-container">
          <div className="overlay">
            <div className="overlay-panel overlay-left">
              <h2>Welcome Back!</h2>
              <p>To keep connected with us please login with your personal info.</p>
              <button
                className="modern-btn ghost"
                onClick={() => setIsRightPanelActive(false)}
              >
                Sign In
              </button>
            </div>
            <div className="overlay-panel overlay-right">
              <h2>Hello, Friend!</h2>
              <p>Enter your personal details and start your journey with MediFormulary.</p>
              <button
                className="modern-btn ghost"
                onClick={() => setIsRightPanelActive(true)}
              >
                Sign Up
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default SignIn;
