import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import './CookieConsent.css';

const CookieConsent = () => {
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Check if user has already made a choice
    const consent = localStorage.getItem('cookieConsent');
    if (!consent) {
      setIsVisible(true);
    }
  }, []);

  const handleAccept = () => {
    localStorage.setItem('cookieConsent', 'accepted');
    setIsVisible(false);
  };

  const handleDecline = () => {
    localStorage.setItem('cookieConsent', 'declined');
    setIsVisible(false);
  };

  const handleSettings = () => {
    // For now, this just hides the banner or could open a modal in the future
    // We'll leave it as hiding it to not block the user, but not setting a strict accepted/declined state
    // Or we can just let it do nothing and require accept/decline.
    // Let's implement it to hide it for now, simulating saving default settings
    localStorage.setItem('cookieConsent', 'settings_saved');
    setIsVisible(false);
  };

  if (!isVisible) return null;

  return (
    <div className="cookie-consent-overlay">
      <div className="cookie-consent-container">
        <div className="cookie-consent-content">
          <p>
            This website uses cookies to improve user's experience, personalise ads and analyse traffic. You can manage your preferences at any time in your <Link to="/settings">Account Settings</Link>. To learn more, view our <Link to="/privacy">cookies policy</Link>.
          </p>
        </div>
        <div className="cookie-consent-actions">
          <button className="btn-cookie-settings" onClick={handleSettings}>
            Cookies settings
          </button>
          <button className="btn-cookie-accept" onClick={handleAccept}>
            Accept all
          </button>
          <button className="btn-cookie-decline" onClick={handleDecline}>
            Decline all
          </button>
        </div>
      </div>
    </div>
  );
};

export default CookieConsent;
