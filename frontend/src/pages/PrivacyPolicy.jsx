import React, { useEffect } from 'react';

const PrivacyPolicy = () => {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="legal-page-wrapper">
      <div className="legal-hero">
        <h1 className="legal-title">Privacy & Cookie Policy</h1>
        <div className="legal-date-badge">Last updated: April 24, 2026</div>
      </div>

      <div className="legal-container">
        <div className="legal-content-card">
          <section>
            <h2>Introduction</h2>
            <p>
              MediFormulary is committed to protecting your privacy. This policy explains how we collect, 
              use, and safeguard your data when you use our platform. We prioritize the security of 
              healthcare data and adhere to industry standards for information protection.
            </p>
          </section>

          <section>
            <h2>Cookies Policy</h2>
            <p>
              We use cookies to improve your experience, personalize content, and analyze our traffic. 
              Cookies are small text files stored on your device that help us provide a seamless clinical workflow.
            </p>
            <ul>
              <li>
                <strong>Essential Cookies</strong>
                <span>Required for the website to function (e.g., authentication and session management).</span>
              </li>
              <li>
                <strong>Preference Cookies</strong>
                <span>Remember your settings such as your selected insurance plan and bookmarked medications.</span>
              </li>
              <li>
                <strong>Analytical Cookies</strong>
                <span>Help us understand how clinicians interact with the platform to improve search accuracy.</span>
              </li>
            </ul>
            <p>
              You can manage your cookie preferences at any time through our cookie consent banner 
              or your browser settings. Disabling essential cookies may limit platform functionality.
            </p>
          </section>

          <section>
            <h2>Data Collection</h2>
            <p>
              We collect information you provide directly to us, such as when you create an account 
              or search for medications. This may include your name, professional email address, 
              clinical role, and institutional affiliation.
            </p>
            <p>
              We do not sell your personal data to third parties. Data is used exclusively to 
              personalize your formulary experience and improve our AI-driven clinical insights.
            </p>
          </section>

          <section>
            <h2>Contact Us</h2>
            <p>
              If you have any questions about this policy or how your data is handled, 
              please contact our Data Protection Office at:
            </p>
            <div style={{ 
              background: 'var(--light-bg)', 
              padding: '1.5rem', 
              borderRadius: '12px', 
              border: '1px solid var(--border-color)',
              fontWeight: '600',
              color: 'var(--accent-color)',
              textAlign: 'center',
              fontSize: '1.2rem'
            }}>
              privacy@mediformulary.ai
            </div>
          </section>
        </div>
      </div>
    </div>
  );
};

export default PrivacyPolicy;
