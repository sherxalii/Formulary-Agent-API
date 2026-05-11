import React, { useState } from 'react';
import { apiRequest } from '../utils/auth';
import toast from 'react-hot-toast';

const Contact = () => {
  const [formData, setFormData] = useState({
    name: '',
    email: '',
    subject: 'general',
    message: '',
  });
  const [loading, setLoading] = useState(false);
  const [submitted, setSubmitted] = useState(false);

  const handleChange = (e) => {
    setFormData({ ...formData, [e.target.name]: e.target.value });
  };

  const handleSubject = (val) => {
    setFormData({ ...formData, subject: val });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    try {
      const res = await apiRequest('POST', '/contact', formData);
      if (res.success) {
        setSubmitted(true);
        toast.success(res.message || 'Message sent! Check your email.');
        setFormData({ name: '', email: '', subject: 'general', message: '' });
        
        setTimeout(() => {
          setSubmitted(false);
        }, 3000);
      } else {
        toast.error(res.error || 'Failed to send message.');
      }
    } catch (err) {
      toast.error('An error occurred. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <main className="biocos-contact-body">
      <div className="biocos-card fade-up delay-1">
        {/* Left Side: Interactive Form */}
        <div className="biocos-left">
          <div className="biocos-header">
            <h1>Get in <span>touch</span></h1>
          </div>
          <p className="biocos-subtitle">
            Say hi to our expert and we'll get back to you as soon as possible!
          </p>

          <form className="biocos-form" id="contactForm" onSubmit={handleSubmit}>
            <div className="input-container">
              <label htmlFor="name">Your full name</label>
              <input
                type="text"
                id="name"
                name="name"
                required
                placeholder="John Doe"
                value={formData.name}
                onChange={handleChange}
                disabled={loading}
              />
            </div>

            <div className="input-container">
              <label htmlFor="email">E-mail</label>
              <input
                type="email"
                id="email"
                name="email"
                required
                placeholder="john@example.com"
                value={formData.email}
                onChange={handleChange}
                disabled={loading}
              />
            </div>

            <div className="input-container">
              <label>Choose Subject</label>
              <div className="subject-group">
                {['general', 'support', 'feedback'].map((val) => (
                  <span
                    key={val}
                    className={`subject-chip${formData.subject === val ? ' active' : ''}`}
                    onClick={() => !loading && handleSubject(val)}
                  >
                    {val.charAt(0).toUpperCase() + val.slice(1) === 'General' ? 'General Inquiry' : val.charAt(0).toUpperCase() + val.slice(1)}
                  </span>
                ))}
              </div>
            </div>

            <div className="input-container">
              <label htmlFor="message">Message</label>
              <textarea
                id="message"
                name="message"
                required
                placeholder="Write your message here..."
                value={formData.message}
                onChange={handleChange}
                disabled={loading}
              />
            </div>

            <button
              type="submit"
              className="biocos-submit"
              disabled={loading}
              style={(submitted || loading) ? { background: 'var(--accent-color)', color: '#fff', opacity: 0.7 } : {}}
            >
              {loading ? 'Sending...' : submitted ? 'Sent!' : 'Send Message'}
            </button>
          </form>
        </div>

        {/* Right Side: Dynamic Visual Element */}
        <div className="biocos-right">
          <div className="abstract-visual">
            <div className="cube"></div>
            <div className="cube"></div>
            <div className="cube"></div>
          </div>
        </div>
      </div>
    </main>
  );
};

export default Contact;
