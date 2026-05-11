import React, { useEffect } from 'react';

const TermsOfService = () => {
  useEffect(() => {
    window.scrollTo(0, 0);
  }, []);

  return (
    <div className="legal-page-wrapper">
      <div className="legal-hero">
        <h1 className="legal-title">Terms of Service</h1>
        <div className="legal-date-badge">Last updated: April 24, 2026</div>
      </div>

      <div className="legal-container">
        <div className="legal-content-card">
          <section>
            <h2>Acceptance of Terms</h2>
            <p>
              By accessing or using MediFormulary, you agree to be bound by these Terms of Service 
              and all applicable laws and regulations. If you do not agree with any of these terms, 
              you are prohibited from using or accessing this site.
            </p>
          </section>

          <section>
            <h2>Use of Service</h2>
            <p>
              MediFormulary is a clinical decision support tool designed for healthcare professionals. 
              The information provided, including formulary status and drug alternatives, is for 
              informational purposes only and does not constitute medical advice.
            </p>
            <ul>
              <li>
                <strong>Clinical Responsibility</strong>
                <span>Clinicians are solely responsible for verifying all information before making clinical decisions.</span>
              </li>
              <li>
                <strong>Data Accuracy</strong>
                <span>While we strive for accuracy, formulary data changes frequently and should be cross-referenced.</span>
              </li>
              <li>
                <strong>Professional Use</strong>
                <span>This tool is intended for use by licensed healthcare practitioners and authorized staff.</span>
              </li>
            </ul>
          </section>

          <section>
            <h2>Account Responsibility</h2>
            <p>
              You are responsible for maintaining the confidentiality of your account credentials 
              and for all activities that occur under your account. You must notify us immediately 
              of any unauthorized use of your account.
            </p>
          </section>

          <section>
            <h2>Modifications</h2>
            <p>
              We reserve the right to modify or replace these terms at any time. We will provide 
              notice of any significant changes. Your continued use of the service after such 
              modifications constitutes your acceptance of the new Terms of Service.
            </p>
          </section>

          <section>
            <h2>Limitation of Liability</h2>
            <p>
              MediFormulary shall not be liable for any damages arising out of the use or inability 
              to use the services, even if we have been notified of the possibility of such damage.
            </p>
          </section>
        </div>
      </div>
    </div>
  );
};

export default TermsOfService;
