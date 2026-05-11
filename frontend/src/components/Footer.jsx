import React, { useEffect } from "react";
import { motion } from "framer-motion";
import { Link } from "react-router-dom";
import { FaLinkedin, FaGithub, FaTwitter } from "react-icons/fa";

const Footer = () => {
  useEffect(() => {
    let ticking = false;

    const handleScroll = () => {
      if (!ticking) {
        requestAnimationFrame(() => {
          const footer = document.querySelector('.footer-glass');
          if (!footer) return;

          const rect = footer.getBoundingClientRect();
          const windowHeight = window.innerHeight;

          let progress = 1 - (rect.top / windowHeight);
          progress = Math.max(0, Math.min(1, progress));

          const blur = 10 + progress * 30;
          footer.style.setProperty('--blur-intensity', `${blur}px`);

          ticking = false;
        });
        ticking = true;
      }
    };

    window.addEventListener('scroll', handleScroll, { passive: true });
    handleScroll();

    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  return (
    <footer className="footer">
      <div className="footer-container">
        <div className="footer-glass">
          <div className="footer-grid">
            <div className="footer-brand">
              <h2 className="footer-title">
                MediFormulary
              </h2>

              <p className="footer-description">
                AI-powered drug intelligence and formulary management platform
                for clinicians to make faster, safer, and coverage-aware decisions.
              </p>

              <div className="footer-social">
                {[FaLinkedin, FaGithub, FaTwitter].map((Icon, i) => (
                  <a
                    key={i}
                    href="#"
                    className="footer-social-link"
                    title="Social Link"
                  >
                    <Icon size={16} />
                  </a>
                ))}
              </div>
            </div>

            <div>
              <h3 className="footer-section-title">
                Product
              </h3>
              <ul className="footer-links">
                <li>
                  <Link className="footer-link" to="/search">
                    AI Drug Search
                  </Link>
                </li>
                <li>
                  <Link className="footer-link" to="/formulary">
                    Formulary Explorer
                  </Link>
                </li>
                <li>
                  <Link className="footer-link" to="/formulary">
                    Clinical Decision Support
                  </Link>
                </li>
                <li>
                  <Link className="footer-link" to="/admin">
                    Database Management
                  </Link>
                </li>
              </ul>
            </div>

            <div>
              <h3 className="footer-section-title">
                Resources
              </h3>
              <ul className="footer-links">
                <li>
                  <a className="footer-link" href="#" target="_blank" rel="noopener noreferrer">
                    Documentation
                  </a>
                </li>
                <li>
                  <a className="footer-link" href="#" target="_blank" rel="noopener noreferrer">
                    API Access
                  </a>
                </li>
                <li>
                  <a className="footer-link" href="#" target="_blank" rel="noopener noreferrer">
                    Guides
                  </a>
                </li>
                <li>
                  <a className="footer-link" href="#" target="_blank" rel="noopener noreferrer">
                    Blog
                  </a>
                </li>
              </ul>
            </div>

            <div>
              <h3 className="footer-section-title">
                Company
              </h3>
              <ul className="footer-links">
                <li>
                  <Link className="footer-link" to="/about">
                    About
                  </Link>
                </li>
                <li>
                  <Link className="footer-link" to="/contact">
                    Contact
                  </Link>
                </li>
                <li>
                  <a className="footer-link" href="#" target="_blank" rel="noopener noreferrer">
                    Careers
                  </a>
                </li>
                <li>
                  <Link className="footer-link" to="/settings">
                    Settings
                  </Link>
                </li>
              </ul>
            </div>
          </div>

          <motion.div
            initial={{ opacity: 0, y: 25 }}
            whileInView={{ opacity: 1, y: 0 }}
            transition={{ duration: 0.4 }}
            className="footer-cta"
          >
            <div>
              <h3 className="footer-cta-title">
                Stay updated with latest drug insights
              </h3>
              <p className="footer-cta-text">
                Get updates on formulary changes and AI-driven clinical insights.
              </p>
            </div>

            <div className="footer-cta-form">
              <input
                type="email"
                placeholder="Enter your email"
                className="footer-input"
              />
              <button className="footer-button">
                Subscribe
              </button>
            </div>
          </motion.div>

          <div className="footer-bottom">
            <p>© 2026 MediFormulary. All rights reserved.</p>

            <div className="footer-bottom-links">
              <Link className="footer-bottom-link" to="/privacy">
                Privacy Policy
              </Link>
              <Link className="footer-bottom-link" to="/terms">
                Terms of Service
              </Link>
            </div>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;
