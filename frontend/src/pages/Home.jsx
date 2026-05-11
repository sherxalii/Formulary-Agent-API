import React, { useState, useEffect, useMemo, useCallback, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { listDatabases, getDatabaseDrugs } from '../api/apiService';
import toast from 'react-hot-toast';
import QuickFormularyModal from '../components/QuickFormularyModal';

const categories = [
  { label: 'Antibiotics', emoji: '', gradient: 'linear-gradient(135deg, #fef5f5 0%, #ffe5e5 100%)', iconBg: '#fee', slug: 'antibiotics' },
  { label: 'Pain Management', emoji: '', gradient: 'linear-gradient(135deg, #f0fdf4 0%, #d1fae5 100%)', iconBg: '#d1fae5', slug: 'pain' },
  { label: 'Cardiovascular', emoji: '', gradient: 'linear-gradient(135deg, #fef2f2 0%, #fecaca 100%)', iconBg: '#fecaca', slug: 'cardiovascular' },
  { label: 'Diabetes', emoji: '', gradient: 'linear-gradient(135deg, #fffbeb 0%, #fed7aa 100%)', iconBg: '#fed7aa', slug: 'diabetes' },
];

const availabilityColors = {
  Formulary: { bg: '#d1fae5', color: '#166534' },
  Restricted: { bg: '#fef3c7', color: '#92400e' },
  'Non Formulary': { bg: '#fee2e2', color: '#991b1b' },
  Unknown: { bg: '#e2e8f0', color: '#334155' },
};

const formIconMap = {
  Tablet: '💊',
  Capsule: '🟡',
  Injection: '💉',
  Inhaler: '🫁',
  Solution: '🧪',
};

const getBookmarks = () => {
  try {
    return JSON.parse(localStorage.getItem('mediformulary_bookmarks') || '[]');
  } catch {
    return [];
  }
};

const saveBookmarks = (items) => {
  localStorage.setItem('mediformulary_bookmarks', JSON.stringify(items));
  window.dispatchEvent(new Event('bookmarksChange'));
};

const MAX_RECENT = 20;

const getRecentlyViewed = () => {
  try {
    return JSON.parse(localStorage.getItem('mediformulary_recently_viewed') || '[]');
  } catch {
    return [];
  }
};

const addToRecentlyViewed = (drug) => {
  const recent = getRecentlyViewed();
  const filtered = recent.filter((d) => d.name !== drug.name);
  const updated = [{ ...drug, viewedAt: Date.now() }, ...filtered].slice(0, MAX_RECENT);
  localStorage.setItem('mediformulary_recently_viewed', JSON.stringify(updated));
  return updated;
};

const DrugCard = React.memo(({ drug, onView, onBookmark, bookmarked }) => {
  const subText = drug.genericName
    ? `${drug.genericName} • ${drug.form}`
    : drug.form;

  const uses = drug.uses || [];
  const salt = drug.salt || drug.strength || "—";
  const drugClass = drug.drugClass || drug.class || "General";
  const drugId = drug.atcCode || drug.rxcui || "RX";

  return (
    <article className="rx-card" role="article">

      {/* ── Top ── */}
      <div className="rx-card-top">
        <span className="rx-num">{drugId}</span>

        <div className="rx-icon-row">
          <div className="rx-pill-icon" aria-hidden="true">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
              <rect x="1" y="6" width="14" height="4" rx="2" fill="#1D9E75" />
              <rect x="1" y="6" width="7" height="4" rx="2" fill="#0F6E56" />
              <line x1="8" y1="6" x2="8" y2="10" stroke="#E1F5EE" strokeWidth="1" />
            </svg>
          </div>
          <div>
            <h3 className="rx-drug-name">{drug.name}</h3>
            <span className="rx-drug-sub">{subText}</span>
          </div>
        </div>

        <div className="rx-status-row">
          <span className="rx-dot" />
          <span className="rx-formulary-text">
            {drug.availability || "Formulary"}
          </span>
          <span className="rx-class-chip">{drugClass}</span>
        </div>
      </div>

      {/* ── Mid ── */}
      <div className="rx-card-mid">
        <div className="rx-field">
          <span className="rx-field-label">Active salt</span>
          <span className="rx-field-value">{salt}</span>
        </div>

        {uses.length > 0 && (
          <div className="rx-field">
            <span className="rx-field-label">Clinical use</span>
            <div className="rx-tags">
              {uses.map((use) => (
                <span key={use} className="rx-tag">{use}</span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* ── Bottom ── */}
      <div className="rx-card-bot">
        <button
          className="rx-btn-main"
          onClick={() => onView(drug.name)}
        >
          Quick Formulary
        </button>
        <button
          className={`rx-btn-icon${bookmarked ? " starred" : ""}`}
          onClick={() => onBookmark(drug)}
          aria-label={bookmarked ? "Remove bookmark" : "Add bookmark"}
        >
          <svg
            width="13"
            height="15"
            viewBox="0 0 13 15"
            fill={bookmarked ? "#1D9E75" : "none"}
            stroke={bookmarked ? "#0F6E56" : "currentColor"}
            strokeWidth="1.3"
            strokeLinejoin="round"
          >
            <path d="M1 1h11v13l-5.5-3.5L1 14V1z" />
          </svg>
        </button>
      </div>

    </article>
  );
});

const Home = () => {
  const navigate = useNavigate();
  const [databases, setDatabases] = useState([]);
  const [selectedDb, setSelectedDb] = useState('');
  const [drugs, setDrugs] = useState([]);
  const [searchQuery, setSearchQuery] = useState('');
  const [activeTab, setActiveTab] = useState('Commonly Prescribed');
  const [bookmarks, setBookmarks] = useState(getBookmarks);
  const [recentlyViewed, setRecentlyViewed] = useState(getRecentlyViewed);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState('');
  const [selectedModalDrug, setSelectedModalDrug] = useState(null);
  const recentScrollRef = useRef(null);

  const selectedDbName = useMemo(() => {
    return databases.find((db) => db.id === selectedDb)?.name || 'Formulary';
  }, [databases, selectedDb]);

  const fetchDatabases = useCallback(async () => {
    const res = await listDatabases();
    if (res.success && res.databases) {
      setDatabases(res.databases);
      const firstDb = res.databases[0]?.id;
      if (firstDb) setSelectedDb(firstDb);
    } else {
      toast.error('Unable to load formularies');
      setError('Unable to load formularies');
    }
  }, []);

  const fetchDrugs = useCallback(async (dbId) => {
    if (!dbId) return;
    setIsLoading(true);
    const res = await getDatabaseDrugs(dbId);
    setIsLoading(false);
    if (res.success) {
      setDrugs(res.drugs || []);
      setError('');
    } else {
      toast.error(res.error || 'Unable to load medications');
      setError(res.error || 'Unable to load medications');
    }
  }, []);

  useEffect(() => {
    fetchDatabases();
  }, [fetchDatabases]);

  useEffect(() => {
    if (selectedDb) fetchDrugs(selectedDb);
  }, [selectedDb, fetchDrugs]);

  const filteredDrugs = useMemo(() => {
    const normalizedQuery = searchQuery.trim().toLowerCase();
    return drugs
      .filter((drug) => {
        if (!normalizedQuery) return true;
        return [
          drug.name,
          drug.genericName,
          drug.drugClass || drug.class,
          drug.form,
          drug.availability,
        ]
          .filter(Boolean)
          .some((value) => value.toLowerCase().includes(normalizedQuery));
      })
      .filter((drug) => {
        if (activeTab === 'Generics') return drug.name.toLowerCase() !== (drug.genericName || '').toLowerCase();
        if (activeTab === 'Brand Names') return drug.name.toLowerCase() === (drug.genericName || '').toLowerCase();
        return true;
      });
  }, [drugs, searchQuery, activeTab]);

  const topDrugs = useMemo(() => filteredDrugs.slice(0, 12), [filteredDrugs]);

  const handleBookmark = useCallback((drug) => {
    const updated = bookmarks.some((item) => item.name === drug.name)
      ? bookmarks.filter((item) => item.name !== drug.name)
      : [...bookmarks, drug];
    setBookmarks(updated);
    saveBookmarks(updated);
  }, [bookmarks]);

  const handleQuickView = useCallback((drugName) => {
    // Track in recently viewed
    const drugObj = drugs.find((d) => d.name === drugName) || recentlyViewed.find((d) => d.name === drugName);
    if (drugObj) {
      const updated = addToRecentlyViewed(drugObj);
      setRecentlyViewed(updated);
      setSelectedModalDrug(drugObj);
    }
  }, [drugs, recentlyViewed]);

  const handleTabChange = useCallback((tab) => {
    setActiveTab(tab);
  }, []);

  const handleClearRecent = useCallback(() => {
    localStorage.removeItem('mediformulary_recently_viewed');
    setRecentlyViewed([]);
  }, []);

  const scrollRecent = useCallback((direction) => {
    if (recentScrollRef.current) {
      const scrollAmount = 320;
      recentScrollRef.current.scrollBy({
        left: direction === 'left' ? -scrollAmount : scrollAmount,
        behavior: 'smooth',
      });
    }
  }, []);

  const availabilityLegend = useMemo(() => Object.keys(availabilityColors), []);

  const formatTimeAgo = (timestamp) => {
    const diff = Date.now() - timestamp;
    const mins = Math.floor(diff / 60000);
    if (mins < 1) return 'Just now';
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    const days = Math.floor(hrs / 24);
    return `${days}d ago`;
  };

  return (
    <>
      <section className="hero hero-home">
        <div className="hero-grid">
          <div className="hero-copy">
            <span className="hero-eyebrow">MediFormulary</span>
            <h1>Access Formularies<br />&amp; Find Medications with Ease.</h1>
            <p>Search, compare, and retrieve prescription drugs quickly and efficiently with our AI-powered formulary assistant.</p>
            <div className="hero-search-card">
              <div className="hero-search-bar">
                <select
                  className="select-pill"
                  value={selectedDb}
                  onChange={(e) => setSelectedDb(e.target.value)}
                  aria-label="Select formulary"
                >
                  {databases.map((db) => (
                    <option key={db.id} value={db.id}>{db.name}</option>
                  ))}
                </select>
                <input
                  className="hero-search-input"
                  type="text"
                  placeholder="Search drugs by name, class, form..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && handleQuickView(searchQuery)}
                  aria-label="Search medications"
                />
                <button className="btn-search hero-search-btn" onClick={() => handleQuickView(searchQuery)}>
                  Search
                </button>
              </div>
              <div className="hero-tabs" role="tablist" aria-label="Drug categories">
                {['Commonly Prescribed', 'Generics', 'Brand Names'].map((tab) => (
                  <button
                    type="button"
                    key={tab}
                    className={`tab-pill${activeTab === tab ? ' active' : ''}`}
                    onClick={() => handleTabChange(tab)}
                    role="tab"
                    aria-selected={activeTab === tab}
                  >
                    {tab}
                  </button>
                ))}
              </div>
            </div>
          </div>
          <div className="hero-visual">
            <div className="visual-card">
              <div className="visual-top">
                <div>
                  <span className="visual-label">Formulary Dashboard</span>
                  <h3>Smart medication overview</h3>
                </div>
                <button className="visual-chip" type="button" onClick={() => window.dispatchEvent(new Event('openAIAssistant'))}>AI Lookup</button>
              </div>
              <div className="visual-grid">
                <div className="visual-panel panel-left">
                  <div className="pill-stack">
                    <div className="pill-icon">💊</div>
                    <div>
                      <h4>Quick Formulary</h4>
                      <p>Search coverage and status instantly.</p>
                    </div>
                  </div>
                  <div className="chart-box">
                    <div className="chart-bar" style={{ height: '88%' }} />
                    <div className="chart-bar" style={{ height: '68%' }} />
                    <div className="chart-bar" style={{ height: '80%' }} />
                  </div>
                </div>
                <div className="visual-panel panel-right">
                  <div className="medicine-illustration" aria-hidden="true">
                    <div className="bottle large" />
                    <div className="bottle small" />
                    <div className="tablet-strip"><span /><span /><span /></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </div>
      </section>

      <main className="container">
        <section className="section categories-section">
          <div className="section-head-row">
            <div>
              <p className="section-eyebrow">Formularies by Drug Class</p>
              <h2>Browse the most searched categories</h2>
            </div>
          </div>
          <div className="category-grid">
            {categories.map((cat) => (
              <button
                key={cat.slug}
                type="button"
                className="category-card"
                style={{ background: cat.gradient }}
                onClick={() => navigate(`/search?category=${cat.slug}`)}
              >
                <div className="category-icon" style={{ backgroundColor: cat.iconBg }}>
                  {cat.emoji}
                </div>
                <div>
                  <h3>{cat.label}</h3>
                </div>
                <span className="category-arrow">→</span>
              </button>
            ))}
          </div>
          <div className="view-all-container">
            <button type="button" className="btn-view-all" onClick={() => navigate('/formulary')}>
              View All Categories →
            </button>
          </div>
        </section>

        {/* ── Featured Safety Tool ── */}
        <section className="section safety-promo-section">
          <div className="safety-promo-card">
            <div className="safety-promo-content">
              <span className="safety-promo-tag">New Feature</span>
              <h2>Drug-Drug Interaction <em>Checker</em></h2>
              <p>Ensure patient safety by instantly identifying potential interactions between medications, including supplements and over-the-counter drugs.</p>
              <button className="safety-promo-btn" onClick={() => navigate('/ddi')}>
                Try the DDI Checker
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M5 12h14M12 5l7 7-7 7" />
                </svg>
              </button>
            </div>
            <div className="safety-promo-visual">
              <div className="safety-icon-box">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                  <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
                  <path d="M12 8v4" /><path d="M12 16h.01" />
                </svg>
              </div>
              <div className="safety-dots">
                <span className="dot dot-1" />
                <span className="dot dot-2" />
                <span className="dot dot-3" />
              </div>
            </div>
          </div>
        </section>

        <section className="section top-meds-section">
          <div className="section-head-row">
            <div>
              <p className="section-eyebrow">Top Medications</p>
              <h2>{selectedDbName} — Popular Drugs</h2>
            </div>
          </div>
          {isLoading ? (
            <div className="loading-state">Loading drugs…</div>
          ) : error ? (
            <div className="empty-state">
              <p>{error}</p>
            </div>
          ) : (
            <div className="medication-grid">
              {topDrugs.length ? topDrugs.map((drug) => (
                <DrugCard
                  key={drug.id || drug.name}
                  drug={drug}
                  bookmarked={bookmarks.some((item) => item.name === drug.name)}
                  onView={handleQuickView}
                  onBookmark={handleBookmark}
                />
              )) : (
                <div className="empty-state">
                  <p>No medications found for this formulary.</p>
                </div>
              )}
            </div>
          )}
        </section>

        {/* ── Recently Viewed Drugs ── */}
        <section className="recently-viewed-section">
          <div className="section-head-row">
            <div>
              <p className="section-eyebrow">Your Activity</p>
              <h2>Recently Viewed Drugs</h2>
            </div>
            <div className="recent-actions">
              {recentlyViewed.length > 0 && (
                <button type="button" className="btn-clear-recent" onClick={handleClearRecent}>
                  Clear All
                </button>
              )}
              <div className="scroll-arrows">
                <button
                  type="button"
                  className="scroll-arrow-btn"
                  onClick={() => scrollRecent('left')}
                  aria-label="Scroll left"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="15 18 9 12 15 6" /></svg>
                </button>
                <button
                  type="button"
                  className="scroll-arrow-btn"
                  onClick={() => scrollRecent('right')}
                  aria-label="Scroll right"
                >
                  <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><polyline points="9 18 15 12 9 6" /></svg>
                </button>
              </div>
            </div>
          </div>

          {recentlyViewed.length === 0 ? (
            <div className="recent-empty">
              <div className="recent-empty-icon">
                <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
                  <circle cx="12" cy="12" r="10" />
                  <polyline points="12 6 12 12 16 14" />
                </svg>
              </div>
              <p>No drugs viewed yet</p>
              <span>Search or browse medications above — they'll appear here for quick access.</span>
            </div>
          ) : (
            <div className="recent-scroll-wrapper">
              <div className="recent-scroll-fade recent-scroll-fade--left" />
              <div className="recent-scroll-track" ref={recentScrollRef}>
                {recentlyViewed.map((drug) => (
                  <div key={drug.name} className="recent-scroll-item">
                    <DrugCard
                      drug={drug}
                      bookmarked={bookmarks.some((item) => item.name === drug.name)}
                      onView={handleQuickView}
                      onBookmark={handleBookmark}
                    />
                  </div>
                ))}
              </div>
              <div className="recent-scroll-fade recent-scroll-fade--right" />
            </div>
          )}
        </section>
      </main>
      <QuickFormularyModal 
        open={!!selectedModalDrug} 
        drug={selectedModalDrug} 
        onClose={() => setSelectedModalDrug(null)} 
      />
    </>
  );
};

export default Home;

