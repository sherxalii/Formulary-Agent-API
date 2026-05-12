import React, { useState, useEffect, useCallback } from 'react';
import { Search, History, Pill, ArrowRight, X } from 'lucide-react';
import { motion, AnimatePresence } from 'framer-motion';
import { useNavigate } from 'react-router-dom';

const CommandK = ({ isOpen, onClose }) => {
  const [query, setQuery] = useState('');
  const [recentSearches, setRecentSearches] = useState([]);
  const navigate = useNavigate();

  useEffect(() => {
    const saved = JSON.parse(localStorage.getItem('mediformulary_recent_searches') || '[]');
    setRecentSearches(saved);
  }, [isOpen]);

  useEffect(() => {
    const handleKeyDown = (e) => {
      if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        isOpen ? onClose() : null; // Parent manages toggle, but we can prevent default
      }
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  const handleSearch = (searchTerm) => {
    if (!searchTerm) return;
    onClose();
    navigate(`/search?q=${encodeURIComponent(searchTerm)}`);
  };

  if (!isOpen) return null;

  return (
    <AnimatePresence>
      <div className="command-k-overlay" onClick={onClose}>
        <motion.div 
          className="command-k-modal"
          initial={{ scale: 0.95, opacity: 0 }}
          animate={{ scale: 1, opacity: 1 }}
          exit={{ scale: 0.95, opacity: 0 }}
          transition={{ duration: 0.2 }}
          onClick={(e) => e.stopPropagation()}
        >
          <div className="command-k-input-wrapper">
            <Search className="text-slate-400" size={20} />
            <input
              autoFocus
              className="command-k-input"
              placeholder="Search medications, classes, or conditions..."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch(query)}
            />
            <button 
              onClick={onClose} 
              className="command-k-close-btn hover-lift"
              aria-label="Close search"
            >
              <X size={20} strokeWidth={2.5} />
            </button>
          </div>

          <div className="command-k-results">
            {query.length > 0 ? (
              <div 
                className="command-k-item" 
                onClick={() => handleSearch(query)}
              >
                <div className="command-k-item-icon">
                  <Search size={20} strokeWidth={2.5} />
                </div>
                <div className="command-k-item-text">
                  <p className="text-slate-800">Search for "{query}"</p>
                  <p className="command-k-item-meta">Instant lookup in global drug databases</p>
                </div>
                <ArrowRight size={18} className="text-slate-300" />
              </div>
            ) : (
              <>
                <div className="command-k-section-title">
                  Recent Activity
                </div>
                {recentSearches.length > 0 ? (
                  recentSearches.map((s, idx) => (
                    <div 
                      key={idx} 
                      className="command-k-item"
                      onClick={() => handleSearch(s)}
                    >
                      <div className="command-k-item-icon">
                        <History size={18} />
                      </div>
                      <div className="command-k-item-text">
                        <span>{s}</span>
                      </div>
                      <ArrowRight size={14} className="text-slate-200 opacity-0 transition-opacity" />
                    </div>
                  ))
                ) : (
                  <div className="px-4 py-8 text-center text-slate-400 italic text-sm">
                    No recent searches yet.
                  </div>
                )}
                
                <div className="command-k-section-title">
                  Quick Actions
                </div>
                <div className="command-k-item" onClick={() => { onClose(); navigate('/ddi'); }}>
                  <div className="command-k-item-icon">
                    <Pill size={18} />
                  </div>
                  <div className="command-k-item-text">
                    <span>Clinical Interaction Checker</span>
                    <p className="command-k-item-meta">Verify DDI safety for patient profiles</p>
                  </div>
                  <ArrowRight size={14} className="text-slate-200" />
                </div>
              </>
            )}
          </div>

          <div className="command-k-footer">
            <span><kbd className="kbd-shortcut">Enter</kbd> <span className="command-k-footer-text">Select</span></span>
            <span><kbd className="kbd-shortcut">Esc</kbd> <span className="command-k-footer-text">Close</span></span>
          </div>
        </motion.div>
      </div>
    </AnimatePresence>
  );
};

export default CommandK;
