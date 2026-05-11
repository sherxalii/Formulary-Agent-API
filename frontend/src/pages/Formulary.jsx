import React, { useState, useEffect, useMemo } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import { listDatabases, getDatabaseDrugs } from '../api/apiService';
import toast from 'react-hot-toast';
import {
  Search,
  Filter,
  ChevronRight,
  ChevronLeft,
  Plus,
  ArrowUpRight,
  Stethoscope,
  LayoutGrid,
  X,
  Download,
  Pill,
  Activity,
  Shield,
  FileText,
  Database,
  Sparkles,
} from 'lucide-react';

const ROWS_PER_PAGE = 10;

const formIconMap = {
  Tablet: <Pill size={14} />,
  Capsule: <Pill size={14} />,
  Inhaler: <Activity size={14} />,
  Solution: <FileText size={14} />,
  Injection: <Shield size={14} />,
};

const tierConfig = [
  { label: 'Tier 1 · Generic', bg: '#E1F5EE', color: '#0F6E56', dot: '#1D9E75' },
  { label: 'Tier 2 · Preferred', bg: '#EBF4FF', color: '#1A56A0', dot: '#3B82F6' },
  { label: 'Tier 3 · Non-preferred', bg: '#FFF8EC', color: '#92400E', dot: '#F59E0B' },
  { label: 'Tier 4 · Specialty', bg: '#FEF0EE', color: '#9B2C1A', dot: '#EF4444' },
];

const Formulary = () => {
  const navigate = useNavigate();
  const [searchParams, setSearchParams] = useSearchParams();
  const [databases, setDatabases] = useState([]);
  const [selectedDb, setSelectedDb] = useState(searchParams.get('db') || '');
  const [drugs, setDrugs] = useState([]);
  const [currentFilter, setCurrentFilter] = useState(searchParams.get('filter') || 'all');
  const [loading, setLoading] = useState(false);
  const [currentPage, setCurrentPage] = useState(1);

  useEffect(() => {
    const fetchDbs = async () => {
      const res = await listDatabases();
      if (res.success && Array.isArray(res.databases)) {
        setDatabases(res.databases);
        const defaultDb = selectedDb || res.databases[0]?.id;
        if (defaultDb) setSelectedDb(defaultDb);
      }
    };
    fetchDbs();
  }, []);

  useEffect(() => {
    if (!selectedDb) return;
    const fetchDrugs = async () => {
      setLoading(true);
      const res = await getDatabaseDrugs(selectedDb);
      setLoading(false);
      if (res.success) {
        setDrugs(res.drugs || []);
      } else {
        toast.error(res.error || 'Unable to load drugs');
      }
    };
    fetchDrugs();
  }, [selectedDb]);

  useEffect(() => {
    setCurrentFilter(searchParams.get('filter') || 'all');
  }, [searchParams]);

  const filteredData = useMemo(() => {
    return drugs.filter((drug) => {
      const matchesFilter = currentFilter === 'all' ||
        [drug.class, drug.name, drug.genericName].filter(Boolean)
          .some((v) => v.toLowerCase().includes(currentFilter.toLowerCase()));
      return matchesFilter;
    });
  }, [drugs, currentFilter]);

  const selectedDbName = useMemo(
    () => databases.find((db) => db.id === selectedDb)?.name || selectedDb,
    [databases, selectedDb]
  );

  const exportCsv = () => {
    const headers = ['Drug Name', 'Generic Name', 'Class', 'Strength', 'Form', 'Availability'];
    const rows = filteredData.map((d) => [d.name, d.genericName, d.class, d.strength, d.form, d.availability]);
    const csv = [headers.join(','), ...rows.map((r) => r.map((v) => `"${v || ''}"`).join(','))].join('\n');
    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `formulary_${selectedDbName.replace(/\s+/g, '_').toLowerCase()}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  const handleDbChange = (db) => {
    setSelectedDb(db);
    setSearchParams({ db, filter: currentFilter });
  };

  const handleFilterByClass = (filter) => {
    const newFilter = currentFilter === filter ? 'all' : filter;
    setCurrentFilter(newFilter);
    setCurrentPage(1);
    setSearchParams({ db: selectedDb, filter: newFilter });
  };

  const totalPages = Math.max(1, Math.ceil(filteredData.length / ROWS_PER_PAGE));
  const pageData = useMemo(
    () => filteredData.slice((currentPage - 1) * ROWS_PER_PAGE, currentPage * ROWS_PER_PAGE),
    [filteredData, currentPage]
  );

  const changePage = (page) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
    window.scrollTo({ top: document.querySelector('.fml-table-section')?.offsetTop - 100, behavior: 'smooth' });
  };

  const startIndex = filteredData.length > 0 ? (currentPage - 1) * ROWS_PER_PAGE + 1 : 0;
  const endIndex = Math.min(currentPage * ROWS_PER_PAGE, filteredData.length);

  const mockIcons = [
    'https://logo.clearbit.com/aetna.com',
    'https://logo.clearbit.com/bcbs.com',
    'https://logo.clearbit.com/uhc.com',
    'https://logo.clearbit.com/cigna.com',
    'https://logo.clearbit.com/humana.com',
  ];

  const getAvailabilityClass = (av) => {
    if (!av || av === 'Formulary') return 'green';
    if (av === 'Restricted') return 'amber';
    return 'red';
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return 'Jan 2026';
    try {
      return new Intl.DateTimeFormat('en-US', { month: 'short', year: 'numeric' }).format(new Date(dateStr));
    } catch {
      return 'Jan 2026';
    }
  };

  return (
    <div className="fml-root">

      {/* ── Hero ── */}
      <section className="fml-hero">
        <div className="fml-hero-inner">
          <div className="fml-hero-badge">
            <Shield size={10} /> Medical Intelligence
          </div>
          <h1 className="fml-hero-title">
            Medical <em>Formularies</em>
          </h1>
          <p className="fml-hero-desc">
            Access the industry's most comprehensive and verified medication lists. Browse
            national, regional, and specialized plans updated in real-time for clinical precision.
          </p>
          <div className="fml-hero-stats">
            <div className="fml-hero-stat">
              <div className="fml-hero-stat-val">{databases.length || '—'}</div>
              <div className="fml-hero-stat-label">Active formularies</div>
            </div>
            <div className="fml-hero-stat">
              <div className="fml-hero-stat-val">
                {drugs.length > 0 ? `${(drugs.length / 1000).toFixed(1)}k` : '—'}
              </div>
              <div className="fml-hero-stat-label">Medications indexed</div>
            </div>
            <div className="fml-hero-stat">
              <div className="fml-hero-stat-val">4</div>
              <div className="fml-hero-stat-label">Coverage tiers</div>
            </div>
          </div>
        </div>
      </section>

      <div className="fml-body">

        {/* ── Search Card ── */}
        <div className="fml-search-card">
          <div className="fml-search-row">
            <div className="fml-filter-col fml-filter-db">
              <label className="fml-filter-label">Explore Formulary</label>
              <div className="fml-input-group">
                <select
                  className="fml-select"
                  value={selectedDb}
                  onChange={(e) => handleDbChange(e.target.value)}
                >
                  <option value="" disabled>Select a formulary to browse</option>
                  {databases.map((db) => (
                    <option key={db.id} value={db.id}>{db.name}</option>
                  ))}
                </select>
                <Filter className="fml-icon-right" size={14} />
              </div>
            </div>

            <div className="fml-pills-container">
              <span className="fml-pills-label">Filter by Therapeutic Class:</span>
              <div className="fml-pills-row">
                {['All', 'Antibiotics', 'Cardiovascular', 'Pain', 'Diabetes', 'Respiratory'].map((label) => {
                  const val = label.toLowerCase();
                  const isActive = currentFilter === val || (currentFilter === 'all' && val === 'all');
                  return (
                    <button
                      key={label}
                      onClick={() => handleFilterByClass(val)}
                      className={`fml-pill ${isActive ? 'active' : ''}`}
                    >
                      {label}
                    </button>
                  );
                })}
              </div>
            </div>
          </div>
        </div>

        {/* ── Grid ── */}
        <div className="fml-section-header">
          <h2 className="fml-section-title">Available Formularies</h2>
          <span className="fml-section-count">{databases.length} plans</span>
        </div>

        <div className="fml-grid">
          {databases.map((plan, i) => {
            const isSelected = selectedDb === plan.id;
            return (
              <div
                key={plan.id}
                onClick={() => handleDbChange(plan.id)}
                className={`fml-card ${isSelected ? 'active' : ''}`}
              >
                <div className="fml-card-badge">Active</div>

                <div className="fml-card-logo-box">
                  <img
                    src={mockIcons[i % mockIcons.length]}
                    alt={plan.name}
                    className="fml-card-logo"
                    onError={(e) => {
                      e.target.style.display = 'none';
                      e.target.parentElement.innerHTML = `<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#9CA3AF" stroke-width="1.5"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="9" y1="13" x2="15" y2="13"/><line x1="9" y1="17" x2="13" y2="17"/></svg>`;
                    }}
                  />
                </div>

                <h3 className="fml-card-title">{plan.name}</h3>
                <p className="fml-card-desc">
                  Comprehensive clinical coverage list updated with the latest efficacy data.
                </p>

                <div className="fml-card-status">
                  <div className="fml-status-dot" />
                  Last updated {formatDate(plan.uploadedAt)} · {plan.drugCount ? `${plan.drugCount.toLocaleString()}+` : '4,200+'} medications
                </div>

                <div className="fml-card-stats">
                  {[
                    { label: 'Total', value: plan.drugCount ? plan.drugCount.toLocaleString() : '0' },
                    { label: 'Generics', value: `${plan.genericPercent || 0}%` },
                    { label: 'Tiers', value: plan.tierCount || '4' },
                  ].map(({ label, value }) => (
                    <div key={label} className="fml-card-stat">
                      <div className="fml-card-stat-label">{label}</div>
                      <div className="fml-card-stat-val">{value}</div>
                    </div>
                  ))}
                </div>

                <div className="fml-card-tiers">
                  {tierConfig.map(({ label, bg, color, dot }) => (
                    <div
                      key={label}
                      className="fml-tier-badge"
                      style={{ background: bg, color }}
                    >
                      <div className="fml-tier-dot" style={{ background: dot }} />
                      {label}
                    </div>
                  ))}
                </div>

                <div className="fml-card-footer" onClick={(e) => { e.stopPropagation(); handleDbChange(plan.id); }}>
                  <span className="fml-card-link" style={{ cursor: 'pointer' }}>Explore medications</span>
                  <div className="fml-card-arrow">
                    <ChevronRight size={16} color="#fff" />
                  </div>
                </div>
              </div>
            );
          })}

          <div className="fml-request-card" onClick={() => navigate('/admin')}>
            <div className="fml-request-icon"><Plus size={22} /></div>
            <div className="fml-request-title">Request Formulary</div>
            <p className="fml-request-desc">
              Don't see your provider? Upload a new formulary via the Admin panel.
            </p>
          </div>
        </div>

        {/* ── Table ── */}
        {selectedDb && (
          <div className="fml-table-section">
            <div className="fml-table-head">
              <div>
                <div className="fml-table-title">Medications — {selectedDbName}</div>
                <div className="fml-table-subtitle">
                  {filteredData.length} drug{filteredData.length !== 1 ? 's' : ''} listed in this formulary
                </div>
              </div>
              <button className="fml-btn-export" onClick={exportCsv}>
                <Download size={14} /> Export CSV
              </button>
            </div>

            <div className="fml-table-wrap">
              <table className="fml-table">
                <thead>
                  <tr>
                    <th>Drug Name</th>
                    <th>Class</th>
                    <th>Strength</th>
                    <th>Form</th>
                    <th>Availability</th>
                  </tr>
                </thead>
                <tbody>
                  {loading ? (
                    <tr>
                      <td colSpan="5">
                        <div className="fml-state-cell">
                          <div className="fml-spinner" />
                          <p className="fml-state-desc">Loading formulary data...</p>
                        </div>
                      </td>
                    </tr>
                  ) : pageData.length === 0 ? (
                    <tr>
                      <td colSpan="5">
                        <div className="fml-state-cell">
                          <div className="fml-state-icon"><Database size={20} /></div>
                          <div className="fml-state-title">No medications found</div>
                          <div className="fml-state-desc">Try adjusting your search or filter criteria.</div>
                        </div>
                      </td>
                    </tr>
                  ) : (
                    pageData.map((drug) => (
                      <tr key={drug.id}>
                        <td>
                          <div className="fml-td-name">{drug.name}</div>
                          <div className="fml-td-generic">{drug.genericName || 'Unknown generic'}</div>
                        </td>
                        <td>
                          <span className="fml-badge-class">{drug.class || 'General'}</span>
                        </td>
                        <td className="fml-td-muted">{drug.strength || '–'}</td>
                        <td>
                          <div className="fml-td-form">
                            <span className="fml-form-icon">
                              {formIconMap[drug.form] || <Pill size={14} />}
                            </span>
                            {drug.form || 'Unknown'}
                          </div>
                        </td>
                        <td>
                          <span className={`fml-badge-status ${getAvailabilityClass(drug.availability)}`}>
                            <span className="fml-badge-dot" />
                            {drug.availability || 'Formulary'}
                          </span>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>

            <div className="fml-table-foot">
              <div className="fml-pagination-info">
                Showing {startIndex}–{endIndex} of {filteredData.length}
              </div>
              {totalPages > 1 && (
                <div className="fml-pagination">
                  <button
                    className="fml-page-btn"
                    onClick={() => changePage(currentPage - 1)}
                    disabled={currentPage === 1}
                  >
                    <ChevronLeft size={14} />
                  </button>
                  {Array.from({ length: totalPages }, (_, i) => i + 1)
                    .filter((p) => p === 1 || p === totalPages || (p >= currentPage - 1 && p <= currentPage + 1))
                    .map((page, idx, arr) => (
                      <React.Fragment key={page}>
                        {idx > 0 && arr[idx - 1] !== page - 1 && (
                          <span className="fml-page-dots">…</span>
                        )}
                        <button
                          className={`fml-page-btn ${page === currentPage ? 'active' : ''}`}
                          onClick={() => changePage(page)}
                        >
                          {page}
                        </button>
                      </React.Fragment>
                    ))}
                  <button
                    className="fml-page-btn"
                    onClick={() => changePage(currentPage + 1)}
                    disabled={currentPage === totalPages}
                  >
                    <ChevronRight size={14} />
                  </button>
                </div>
              )}
            </div>
          </div>
        )}

        {/* ── CTA ── */}
        <div className="fml-cta">
          <div>
            <div className="fml-cta-tag">
              <div className="fml-cta-icon-sm">
                <Sparkles size={9} color="#4ADE80" />
              </div>
              AI-Powered Lookup
            </div>
            <h2 className="fml-cta-title">Predictive Formulary<br />Matching</h2>
            <p className="fml-cta-desc">
              Upload patient demographics and medication history to automatically identify
              the lowest-cost, most effective coverage option across all available formularies.
            </p>
            <button className="fml-cta-btn" onClick={() => navigate('/search')}>
              Explore Clinical Insights <ArrowUpRight size={16} />
            </button>
          </div>
          <div className="fml-cta-graphic">
            <div className="fml-cta-inner-dot">
              <Stethoscope size={20} color="#4ADE80" />
            </div>
          </div>
        </div>

      </div>
    </div>
  );
};

export default Formulary;
