import React, { useState, useEffect, useMemo, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  AlertTriangle,
  Search as SearchIcon,
  FileText,
  X,
  Check,
  PlusCircle,
  ChevronDown,
  ChevronUp,
  Activity,
  Layout,
  ShieldCheck,
  SlidersHorizontal
} from 'lucide-react';
import * as api from '../api/apiService';
import { toast } from 'react-hot-toast';
import DrugCard from '../components/DrugCard';
import QuickFormularyModal from '../components/QuickFormularyModal';

const RESULTS_PER_PAGE = 10;

const commonConditions = ['Asthma', 'Hypertension', 'Diabetes', 'Arthritis', 'Depression', 'Anxiety', 'Migraine', 'Eczema'];
const commonMedications = ['Lisinopril', 'Metformin', 'Aspirin', 'Albuterol', 'Omeprazole', 'Simvastatin', 'Ibuprofen'];
const commonAllergies = ['Penicillin', 'Sulfonamides', 'NSAIDs', 'Acetaminophen', 'Anticonvulsants'];

const filterGroups = [
  {
    label: 'Coverage',
    name: 'coverage',
    options: [
      { value: 'formulary', label: 'Covered' },
      { value: 'not_insured', label: 'Not Covered' },
    ],
  },
  {
    label: 'Form',
    name: 'form',
    options: [
      { value: 'tablet', label: 'Tablet' },
      { value: 'capsule', label: 'Capsule' },
      { value: 'inhaler', label: 'Inhaler' },
      { value: 'solution', label: 'Solution' },
      { value: 'injection', label: 'Injection' },
    ],
  },
  {
    label: 'Drug Type',
    name: 'type',
    options: [
      { value: 'generic', label: 'Generic' },
      { value: 'brand', label: 'Brand' },
    ],
  },
];

const statusClassMap = {
  Formulary: 'status-formulary',
  Alternative: 'status-restricted',
  'Not Covered': 'status-non-formulary',
};

const saveBookmarks = (items) => {
  localStorage.setItem('mediformulary_bookmarks', JSON.stringify(items));
  window.dispatchEvent(new Event('bookmarksChange'));
};

const Search = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const [query, setQuery] = useState(searchParams.get('q') || '');
  const [selectedDb, setSelectedDb] = useState(searchParams.get('db') || '');
  const [patientId, setPatientId] = useState(searchParams.get('pid') || 'PAT-001');
  const [databases, setDatabases] = useState([]);
  const [allResults, setAllResults] = useState([]);
  const [results, setResults] = useState([]);
  const [checkedFilters, setCheckedFilters] = useState({});
  const [activeTab, setActiveTab] = useState('Commonly Prescribed');
  const [currentPage, setCurrentPage] = useState(1);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [searchMeta, setSearchMeta] = useState({
    isInsured: false,
    correctedDrugName: '',
    message: '',
    searchedDrug: '',
  });

  const [expandedForm, setExpandedForm] = useState(false);
  const [patientData, setPatientData] = useState({
    conditions: searchParams.get('cond')?.split(',').filter(Boolean) || [],
    allergies: searchParams.get('alg')?.split(',').filter(Boolean) || [],
    current_medications: [],
    pregnancy_status: 'not_pregnant',
    alcohol_use: 'no',
    age_group: 'adult'
  });

  const [conditionInput, setConditionInput] = useState('');
  const [medicationInput, setMedicationInput] = useState('');
  const [allergyInput, setAllergyInput] = useState('');

  const [bookmarks, setBookmarks] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('mediformulary_bookmarks') || '[]');
    } catch {
      return [];
    }
  });
  const [selectedModalDrug, setSelectedModalDrug] = useState(null);

  const [recentSearches, setRecentSearches] = useState(() => {
    try {
      return JSON.parse(localStorage.getItem('mediformulary_recent_searches') || '[]');
    } catch {
      return [];
    }
  });

  // Autocomplete suggestions state
  const [suggestions, setSuggestions] = useState([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [highlightedIndex, setHighlightedIndex] = useState(-1);

  // Debounced autocomplete effect
  useEffect(() => {
    const fetchSuggestions = async () => {
      if (query.length < 2) {
        setSuggestions([]);
        return;
      }

      try {
        const res = await api.getAutocomplete(query);
        if (res.success) {
          setSuggestions(res.results);
        }
      } catch (err) {
        console.error("Autocomplete failed", err);
      }
    };

    const timer = setTimeout(fetchSuggestions, 300);
    return () => clearTimeout(timer);
  }, [query]);

  const addField = (field, value) => {
    if (value.trim()) {
      setPatientData(prev => ({
        ...prev,
        [field]: [...prev[field], value.trim()]
      }));
      if (field === 'conditions') setConditionInput('');
      if (field === 'current_medications') setMedicationInput('');
      if (field === 'allergies') setAllergyInput('');
    }
  };

  const removeField = (field, index) => {
    setPatientData(prev => ({
      ...prev,
      [field]: prev[field].filter((_, i) => i !== index)
    }));
  };

  const applyFilters = useCallback((baseResults, filters) => {
    if (!filters || Object.keys(filters).every((key) => !filters[key]?.length)) {
      return baseResults;
    }

    return baseResults.filter((drug) => {
      return Object.entries(filters).every(([filterName, filterValues]) => {
        if (!filterValues || filterValues.length === 0) return true;

        if (filterName === 'coverage') {
          return filterValues.some((filterValue) => {
            if (filterValue === 'formulary') return drug.isInsured === true;
            if (filterValue === 'not_insured') return drug.isInsured === false;
            return false;
          });
        }

        if (filterName === 'type') {
          if (!drug.genericName) return false;
          const isGeneric = drug.name.toLowerCase() === drug.genericName.toLowerCase();
          return filterValues.some((filterValue) => (filterValue === 'generic' ? isGeneric : !isGeneric));
        }

        const value = String(drug[filterName] || '').toLowerCase();
        return filterValues.some((filterValue) => value.includes(filterValue.toLowerCase()));
      });
    });
  }, []);

  const fetchDatabases = useCallback(async () => {
    try {
      const res = await api.listDatabases();
      if (res.success && Array.isArray(res.databases)) {
        setDatabases(res.databases);
        // Use functional update to avoid dependency on selectedDb
        setSelectedDb(prev => {
          if (!prev && res.databases.length > 0) return res.databases[0].id;
          return prev;
        });
      }
    } catch (err) {
      console.error("Failed to fetch databases", err);
    }
  }, []); // NO dependencies here

  const performSearch = useCallback(
    async (searchText, db, pid, pData) => {
      if (!searchText.trim() || !db) {
        return;
      }

      setIsLoading(true);
      setError(null);
      setResults([]);
      setAllResults([]);
      setSearchMeta({ isInsured: false, correctedDrugName: '', message: '', searchedDrug: '', safestRecommendation: null });
      try {
        const res = await api.getAlternatives(searchText, db, pid, pData);
        if (!res.success) {
          setError(res.error || 'Failed to fetch formulary information');
          toast.error(res.error || 'Search failed');
          setAllResults([]);
          setResults([]);
          setSearchMeta({ isInsured: false, correctedDrugName: '', message: '', searchedDrug: searchText.trim() });
          return;
        }

        const isInsured = res.primary_indication === 'INSURED';
        const correctedDrugName = res.corrected_drug_name || searchText.trim();

        let rawAlternatives = res.alternatives || [];

        const baseResults = isInsured
          ? [
            {
              id: `insured-${Date.now()}`,
              name: searchText.trim(),
              genericName: correctedDrugName,
              strength: 'N/A',
              form: 'N/A',
              class: 'Prescribed',
              availability: 'Formulary',
              isInsured: true,
              coverage: 'formulary',
              note: res.rxnorm_validation_message || 'This medication is covered by the selected formulary.',
            },
          ]
          : rawAlternatives.map((alt, idx) => ({
            id: `alt-${idx}-${Date.now()}`,
            name: alt.drug_name,
            genericName: alt.generic_name || 'Generic',
            strength: alt.strength || 'N/A',
            form: alt.medicine_form || 'N/A',
            class: 'Alternative',
            availability: 'Alternative',
            isInsured: false,
            coverage: 'not_insured',
            note: res.rxnorm_validation_message || 'Review these covered alternatives for the selected plan.',
            safe: alt.safe,
            safety_alerts: alt.safety_alerts,
            safety_score: alt.safety_score,
            rating: alt.rating,
            pregnancy_safe: alt.pregnancy_safe
          }));

        // Find the absolute safest alternative (highest safety_score)
        let safestRecommendation = null;
        if (!isInsured && baseResults.length > 0) {
          safestRecommendation = [...baseResults].sort((a, b) => (b.safety_score || 0) - (a.safety_score || 0))[0];
          // Only recommend if it's actually "safe" (score > 80)
          if (safestRecommendation.safety_score < 80) safestRecommendation = null;
        }

        setAllResults(baseResults);
        setResults(applyFilters(baseResults, checkedFilters));
        setSearchMeta({
          isInsured,
          correctedDrugName,
          message: res.patient_safety_summary || res.rxnorm_validation_message || (isInsured ? 'Covered by formulary.' : 'Safe alternatives found using ML verification.'),
          searchedDrug: searchText.trim(),
          safestRecommendation
        });
        setCurrentPage(1);
      } catch (err) {
        console.error(err);
        setError('An unexpected error occurred while searching.');
      } finally {
        setIsLoading(false);
      }
    },
    [applyFilters, checkedFilters]
  );

  useEffect(() => {
    fetchDatabases();
  }, [fetchDatabases]);

  useEffect(() => {
    const q = searchParams.get('q') || '';
    const db = searchParams.get('db') || '';
    const pid = searchParams.get('pid') || 'PAT-001';
    const cond = searchParams.get('cond') || '';
    const alg = searchParams.get('alg') || '';

    // Only update states if they actually changed to prevent loops
    if (q !== query) setQuery(q);
    if (db && db !== selectedDb) setSelectedDb(db);
    if (pid !== patientId) setPatientId(pid);

    if (q && (db || selectedDb)) {
      const targetDb = db || selectedDb;
      performSearch(q, targetDb, pid, patientData);
    } else if (!q) {
      setResults([]);
      setAllResults([]);
      setSearchMeta({ isInsured: false, correctedDrugName: '', message: '', searchedDrug: '', safestRecommendation: null });
    }
    // We remove selectedDb and patientId from dependencies as we handle them inside handleSearch/setSearchParams
  }, [searchParams, performSearch]);

  const handleSearch = () => {
    if (!query.trim()) {
      toast.error('Please enter a drug name to search.');
      return;
    }
    if (!selectedDb) {
      toast.error('Please select an insurance formulary.');
      return;
    }

    // Save to recent searches
    const newRecent = [query.trim(), ...recentSearches.filter(s => s !== query.trim())].slice(0, 5);
    setRecentSearches(newRecent);
    localStorage.setItem('mediformulary_recent_searches', JSON.stringify(newRecent));

    setSearchParams({
      q: query,
      db: selectedDb,
      pid: patientId,
      cond: patientData.conditions.join(','),
      alg: patientData.allergies.join(',')
    });
  };


  const handleFilterChange = (groupName, value, checked) => {
    const next = { ...checkedFilters };
    const current = next[groupName] || [];
    next[groupName] = checked ? [...current, value] : current.filter((item) => item !== value);
    setCheckedFilters(next);
    setResults(applyFilters(allResults, next));
    setCurrentPage(1);
  };

  const toggleBookmark = (drug) => {
    const existing = bookmarks.find((item) => item.name === drug.name);
    const updated = existing ? bookmarks.filter((item) => item.name !== drug.name) : [...bookmarks, drug];
    saveBookmarks(updated);
    setBookmarks(updated);
  };

  const isBookmarked = (name) => bookmarks.some((item) => item.name === name);

  const handleQuickView = useCallback((drugName) => {
    const drugObj = allResults.find(d => d.name === drugName);
    if (drugObj) {
      setSelectedModalDrug(drugObj);
    }
  }, [allResults]);

  const totalPages = Math.max(1, Math.ceil(results.length / RESULTS_PER_PAGE));
  const pageData = useMemo(
    () => results.slice((currentPage - 1) * RESULTS_PER_PAGE, currentPage * RESULTS_PER_PAGE),
    [results, currentPage]
  );

  const changePage = (page) => {
    if (page < 1 || page > totalPages) return;
    setCurrentPage(page);
    window.scrollTo({ top: 0, behavior: 'smooth' });
  };

  const summaryText = searchMeta.searchedDrug
    ? searchMeta.isInsured
      ? `${searchMeta.searchedDrug} is covered by this formulary.`
      : `${searchMeta.searchedDrug} is not covered. Suggested covered alternatives appear below.`
    : 'Search for a medication to see coverage results and recommendations.';

  return (
    <div className="search-page-container">
      <div className="search-hero" style={{
        padding: '6rem 2rem 5rem',
        background: 'linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%)',
        position: 'relative',
        borderBottom: '1px solid #e2e8f0'
      }}>
        {/* Decorative background element */}
        <div style={{ position: 'absolute', top: 0, left: 0, right: 0, bottom: 0, overflow: 'hidden', pointerEvents: 'none' }}>
          <div style={{
            position: 'absolute',
            top: '-10%',
            right: '-5%',
            width: '400px',
            height: '400px',
            background: 'radial-gradient(circle, rgba(22, 160, 133, 0.05) 0%, transparent 70%)',
            filter: 'blur(60px)'
          }} />
        </div>

        <h1 style={{ fontSize: '3rem', fontWeight: 900, letterSpacing: '-0.03em', marginBottom: '1rem', color: '#0f172a' }}>
          Find Any Medication Instantly
        </h1>
        <p style={{ fontSize: '1.125rem', color: '#64748b', maxWidth: '600px', margin: '0 auto 3.5rem', lineHeight: 1.6 }}>
          Advanced AI-powered formulary search with real-time clinical safety verification.
        </p>

        <div className="search-container" style={{ maxWidth: '950px', margin: '0 auto', position: 'relative', zIndex: 1000 }}>
          <div className="search-box-premium" style={{
            background: '#ffffff',
            padding: '10px',
            borderRadius: '24px',
            display: 'flex',
            alignItems: 'center',
            gap: '12px',
            boxShadow: '0 25px 70px rgba(15, 23, 42, 0.08)',
            border: '1px solid #e2e8f0'
          }}>
            <div className="dropdown-wrapper" style={{
              minWidth: '240px',
              padding: '0 16px',
              borderRight: '1.5px solid #f1f5f9',
              display: 'flex',
              alignItems: 'center',
              gap: '10px'
            }}>
              <Layout size={18} style={{ color: '#64748b' }} />
              <select
                className="dropdown-btn-premium"
                value={selectedDb}
                onChange={(e) => setSelectedDb(e.target.value)}
                style={{
                  background: 'transparent',
                  border: 'none',
                  width: '100%',
                  fontSize: '0.9375rem',
                  fontWeight: 600,
                  color: '#1e293b',
                  cursor: 'pointer',
                  outline: 'none',
                  padding: '8px 0'
                }}
              >
                <option value="" disabled>Select Insurance Plan</option>
                {databases.map((db) => (
                  <option key={db.id} value={db.id}>{db.name}</option>
                ))}
              </select>
            </div>

            <div style={{ flex: 1, display: 'flex', alignItems: 'center', padding: '0 12px', position: 'relative' }}>
              <SearchIcon size={20} style={{ color: '#94a3b8', marginRight: '12px' }} />
              <input
                type="text"
                className="search-input-premium"
                placeholder="Search drug (e.g., Atorvastatin)..."
                value={query}
                onChange={(e) => {
                  const val = e.target.value;
                  setQuery(val);
                  setShowSuggestions(true);
                  if (!val.trim()) {
                    setResults([]);
                    setAllResults([]);
                    setSearchMeta({ isInsured: false, correctedDrugName: '', message: '', searchedDrug: '', safestRecommendation: null });
                  }
                }}
                onFocus={() => setShowSuggestions(true)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter') {
                    if (highlightedIndex >= 0 && suggestions[highlightedIndex]) {
                      setQuery(suggestions[highlightedIndex].name);
                    } else {
                      handleSearch();
                    }
                    setShowSuggestions(false);
                  } else if (e.key === 'ArrowDown') {
                    setHighlightedIndex(prev => Math.min(prev + 1, suggestions.length - 1));
                  } else if (e.key === 'ArrowUp') {
                    setHighlightedIndex(prev => Math.max(prev - 1, -1));
                  } else if (e.key === 'Escape') {
                    setShowSuggestions(false);
                  }
                }}
                style={{
                  width: '100%',
                  border: 'none',
                  fontSize: '1.0625rem',
                  fontWeight: 500,
                  color: '#0f172a',
                  background: 'transparent',
                  outline: 'none'
                }}
              />
              
              {/* Autocomplete Dropdown */}
              {showSuggestions && suggestions.length > 0 && (
                <div style={{
                  position: 'absolute',
                  top: '100%',
                  left: 0,
                  right: 0,
                  marginTop: '15px',
                  background: 'white',
                  borderRadius: '16px',
                  boxShadow: '0 15px 40px rgba(0,0,0,0.12)',
                  zIndex: 1000,
                  border: '1px solid #e2e8f0',
                  maxHeight: '350px',
                  overflowY: 'auto',
                  animation: 'fadeIn 0.2s ease-out'
                }}>
                  {suggestions.map((item, idx) => (
                    <div
                      key={idx}
                      onClick={() => {
                        setQuery(item.name);
                        setShowSuggestions(false);
                      }}
                      onMouseOver={() => setHighlightedIndex(idx)}
                      style={{
                        padding: '12px 20px',
                        cursor: 'pointer',
                        background: highlightedIndex === idx ? '#f8fafc' : 'transparent',
                        borderBottom: idx === suggestions.length - 1 ? 'none' : '1px solid #f1f5f9',
                        display: 'flex',
                        flexDirection: 'column',
                        transition: 'all 0.15s'
                      }}
                    >
                      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                        <span style={{ fontWeight: 700, color: '#1e293b', fontSize: '0.95rem' }}>{item.name}</span>
                        {item.rating > 0 && (
                          <span style={{ fontSize: '0.75rem', color: '#16a085', fontWeight: 800 }}>★ {item.rating.toFixed(1)}</span>
                        )}
                      </div>
                      <div style={{ fontSize: '0.75rem', color: '#64748b', marginTop: '2px', display: 'flex', gap: '8px' }}>
                        <span>Generic: {item.genericName}</span>
                        <span>•</span>
                        <span>{item.condition}</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <button
              className="btn-search-premium"
              onClick={handleSearch}
              disabled={isLoading}
              style={{
                background: 'linear-gradient(135deg, #16a085 0%, #12876f 100%)',
                color: 'white',
                borderRadius: '16px',
                padding: '12px 32px',
                display: 'flex',
                alignItems: 'center',
                gap: '10px',
                border: 'none',
                fontSize: '1rem',
                fontWeight: 700,
                cursor: 'pointer',
                boxShadow: '0 10px 25px rgba(22, 160, 133, 0.2)',
                transition: 'all 0.3s ease'
              }}
            >
              {isLoading ? '...' : <><SearchIcon size={18} strokeWidth={2.5} /> Search</>}
            </button>
          </div>

          {/* Recent Searches */}
          {recentSearches.length > 0 && (
            <div style={{ 
              marginTop: '1.5rem', 
              display: 'flex', 
              alignItems: 'center', 
              justifyContent: 'center',
              gap: '12px',
              flexWrap: 'wrap'
            }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: '#94a3b8', textTransform: 'uppercase', letterSpacing: '0.05em' }}>Recent:</span>
              {recentSearches.map((s, idx) => (
                <button
                  key={idx}
                  onClick={() => { setQuery(s); handleSearch(); }}
                  style={{
                    background: 'rgba(255, 255, 255, 0.8)',
                    border: '1px solid #e2e8f0',
                    borderRadius: '100px',
                    padding: '4px 14px',
                    fontSize: '0.85rem',
                    color: '#64748b',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    fontWeight: 500
                  }}
                  onMouseOver={(e) => { e.target.style.background = '#fff'; e.target.style.borderColor = '#cbd5e1'; e.target.style.color = '#334155'; }}
                  onMouseOut={(e) => { e.target.style.background = 'rgba(255, 255, 255, 0.8)'; e.target.style.borderColor = '#e2e8f0'; e.target.style.color = '#64748b'; }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          <div style={{ marginTop: '2rem', display: 'flex', justifyContent: 'center' }}>
            <button
              onClick={() => setExpandedForm(!expandedForm)}
              style={{
                background: expandedForm ? '#f1f5f9' : 'white',
                border: '1px solid #e2e8f0',
                color: '#475569',
                cursor: 'pointer',
                fontSize: '0.8125rem',
                fontWeight: 700,
                padding: '10px 24px',
                borderRadius: '100px',
                display: 'inline-flex',
                alignItems: 'center',
                gap: '10px',
                transition: 'all 0.3s cubic-bezier(0.4, 0, 0.2, 1)',
                textTransform: 'uppercase',
                letterSpacing: '0.06em',
                boxShadow: '0 4px 12px rgba(15, 23, 42, 0.05)'
              }}
            >
              <div style={{
                width: '8px',
                height: '8px',
                borderRadius: '50%',
                background: expandedForm ? '#16a085' : '#94a3b8',
                boxShadow: expandedForm ? '0 0 10px #16a085' : 'none',
                transition: 'all 0.3s'
              }} />
              {expandedForm ? 'Hide Clinical Context' : 'Add Patient Context (ML Safety)'}
              {expandedForm ? <X size={14} style={{ marginLeft: '4px' }} /> : <ChevronDown size={14} style={{ marginLeft: '4px' }} />}
            </button>
          </div>
        </div>
      </div>

      {/* Patient Data Form - Collapsible */}
      {expandedForm && (
        <div style={{
          backgroundColor: '#ffffff',
          padding: '2.5rem',
          borderRadius: '30px',
          margin: '2rem auto',
          maxWidth: '1200px',
          boxShadow: '0 25px 60px rgba(0,0,0,0.1)',
          border: '1px solid #eef2f6',
          position: 'relative',
          animation: 'fadeIn 0.3s ease-out'
        }}>
          {/* Top Hide Button */}
          <button
            onClick={() => setExpandedForm(false)}
            style={{
              position: 'absolute',
              right: '24px',
              top: '24px',
              width: '36px',
              height: '36px',
              borderRadius: '50%',
              background: '#f8fafc',
              border: '1px solid #e2e8f0',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              cursor: 'pointer',
              color: '#64748b',
              transition: 'all 0.2s'
            }}
            title="Hide Form"
          >
            <X size={20} />
          </button>

          <h2 style={{ fontSize: '1.625rem', fontWeight: 900, letterSpacing: '-0.02em', marginBottom: '2.5rem', color: '#0f172a', display: 'flex', alignItems: 'center', gap: '14px' }}>
            <ShieldCheck size={32} style={{ color: '#16a085' }} />
            Patient Health Profile
            <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: '8px', marginRight: '48px' }}>
              <span style={{
                fontSize: '0.75rem',
                fontWeight: 800,
                color: '#16a085',
                background: 'rgba(22, 160, 133, 0.1)',
                padding: '4px 12px',
                borderRadius: '100px',
                textTransform: 'uppercase',
                letterSpacing: '0.05em'
              }}>
                ML Safety Engine Active
              </span>
            </div>
          </h2>

          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '2rem' }}>

            {/* Medical Conditions */}
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem', color: '#475569' }}>Medical Conditions</label>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <input
                  type="text"
                  placeholder="e.g., Asthma"
                  value={conditionInput}
                  onChange={(e) => setConditionInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addField('conditions', conditionInput))}
                  list="conditions-list"
                  className="search-input"
                  style={{ flex: 1, padding: '10px 14px', fontSize: '0.875rem', height: 'auto', background: '#f8fafc' }}
                />
                <datalist id="conditions-list">
                  {commonConditions.map(c => <option key={c} value={c} />)}
                </datalist>
                <button
                  type="button"
                  onClick={() => addField('conditions', conditionInput)}
                  className="btn-search"
                  style={{ padding: '0 16px', fontSize: '0.875rem', minWidth: 'auto', background: 'var(--accent-color)' }}
                >
                  Add
                </button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {patientData.conditions.map((cond, idx) => (
                  <div key={idx} className="rx-tag" style={{ background: '#f1f5f9', color: '#334155', padding: '6px 12px', fontSize: '0.75rem' }}>
                    {cond}
                    <button onClick={() => removeField('conditions', idx)} style={{ marginLeft: '6px', border: 'none', background: 'none', cursor: 'pointer' }}>
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Current Medications */}
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem', color: '#475569' }}>Current Medications (for DDI Check)</label>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <input
                  type="text"
                  placeholder="e.g., Lisinopril"
                  value={medicationInput}
                  onChange={(e) => setMedicationInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addField('current_medications', medicationInput))}
                  list="medications-list"
                  className="search-input"
                  style={{ flex: 1, padding: '10px 14px', fontSize: '0.875rem', height: 'auto', background: '#f8fafc' }}
                />
                <datalist id="medications-list">
                  {commonMedications.map(m => <option key={m} value={m} />)}
                </datalist>
                <button
                  type="button"
                  onClick={() => addField('current_medications', medicationInput)}
                  className="btn-search"
                  style={{ padding: '0 16px', fontSize: '0.875rem', minWidth: 'auto', background: 'var(--secondary-color)' }}
                >
                  Add
                </button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {patientData.current_medications.map((med, idx) => (
                  <div key={idx} className="rx-tag" style={{ background: '#fef3c7', color: '#92400e', border: '1px solid #fde68a', padding: '6px 12px', fontSize: '0.75rem' }}>
                    {med}
                    <button onClick={() => removeField('current_medications', idx)} style={{ marginLeft: '6px', border: 'none', background: 'none', cursor: 'pointer' }}>
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Allergies */}
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem', color: '#475569' }}>Known Allergies</label>
              <div style={{ display: 'flex', gap: '0.5rem', marginBottom: '0.75rem' }}>
                <input
                  type="text"
                  placeholder="e.g., Penicillin"
                  value={allergyInput}
                  onChange={(e) => setAllergyInput(e.target.value)}
                  onKeyDown={(e) => e.key === 'Enter' && (e.preventDefault(), addField('allergies', allergyInput))}
                  list="allergies-list"
                  className="search-input"
                  style={{ flex: 1, padding: '10px 14px', fontSize: '0.875rem', height: 'auto', background: '#f8fafc' }}
                />
                <datalist id="allergies-list">
                  {commonAllergies.map(a => <option key={a} value={a} />)}
                </datalist>
                <button
                  type="button"
                  onClick={() => addField('allergies', allergyInput)}
                  className="btn-search"
                  style={{ padding: '0 16px', fontSize: '0.875rem', minWidth: 'auto', background: '#ef4444' }}
                >
                  Add
                </button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem' }}>
                {patientData.allergies.map((allergy, idx) => (
                  <div key={idx} className="rx-tag" style={{ background: '#fee2e2', color: '#991b1b', border: '1px solid #fecaca', padding: '6px 12px', fontSize: '0.75rem' }}>
                    {allergy}
                    <button onClick={() => removeField('allergies', idx)} style={{ marginLeft: '6px', border: 'none', background: 'none', cursor: 'pointer' }}>
                      <X size={12} />
                    </button>
                  </div>
                ))}
              </div>
            </div>

            {/* Pregnancy Status */}
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem', color: '#475569' }}>Pregnancy Status</label>
              <select
                className="dropdown-btn"
                value={patientData.pregnancy_status}
                onChange={(e) => setPatientData({ ...patientData, pregnancy_status: e.target.value })}
                style={{ width: '100%', padding: '10px 14px', fontSize: '0.875rem', height: 'auto', border: '1px solid #e2e8f0' }}
              >
                <option value="not_pregnant">Not Pregnant</option>
                <option value="pregnant">Pregnant</option>
                <option value="breastfeeding">Breastfeeding</option>
              </select>
            </div>

            {/* Alcohol Use */}
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem', color: '#475569' }}>Alcohol Consumption</label>
              <select
                className="dropdown-btn"
                value={patientData.alcohol_use}
                onChange={(e) => setPatientData({ ...patientData, alcohol_use: e.target.value })}
                style={{ width: '100%', padding: '10px 14px', fontSize: '0.875rem', height: 'auto', border: '1px solid #e2e8f0' }}
              >
                <option value="no">No</option>
                <option value="occasional">Occasional</option>
                <option value="regular">Regular</option>
                <option value="heavy">Heavy</option>
              </select>
            </div>

            {/* Age Group */}
            <div>
              <label style={{ display: 'block', fontSize: '0.875rem', fontWeight: 600, marginBottom: '0.75rem', color: '#475569' }}>Age Group</label>
              <select
                className="dropdown-btn"
                value={patientData.age_group}
                onChange={(e) => setPatientData({ ...patientData, age_group: e.target.value })}
                style={{ width: '100%', padding: '10px 14px', fontSize: '0.875rem', height: 'auto', border: '1px solid #e2e8f0' }}
              >
                <option value="pediatric">Pediatric (0-17)</option>
                <option value="adult">Adult (18-64)</option>
                <option value="geriatric">Geriatric (65+)</option>
              </select>
            </div>
          </div>

          <div style={{
            marginTop: '2rem',
            paddingTop: '2rem',
            borderTop: '1px solid #f1f5f9',
            display: 'flex',
            justifyContent: 'flex-end',
            gap: '12px'
          }}>
            <button
              onClick={() => setPatientData({
                medical_conditions: [],
                current_medications: [],
                pregnancy_status: 'not_pregnant',
                allergies: [],
                alcohol_use: 'no',
                age_group: 'adult'
              })}
              style={{
                padding: '10px 24px',
                borderRadius: '12px',
                background: 'white',
                color: '#ef4444',
                fontWeight: 700,
                border: '1px solid #fee2e2',
                cursor: 'pointer'
              }}
            >
              Clear All Data
            </button>
            <button
              onClick={() => setExpandedForm(false)}
              style={{
                padding: '10px 24px',
                borderRadius: '12px',
                background: '#f8fafc',
                color: '#475569',
                fontWeight: 700,
                border: '1px solid #e2e8f0',
                cursor: 'pointer',
                display: 'flex',
                alignItems: 'center',
                gap: '8px'
              }}
            >
              <ChevronUp size={18} />
              Hide Profile Form
            </button>
          </div>
        </div>
      )}

      {searchMeta.searchedDrug && (
        <div style={{
          marginTop: '2rem',
          padding: '1.5rem',
          background: '#ffffff',
          borderRadius: '24px',
          boxShadow: '0 10px 40px rgba(15, 23, 42, 0.05)',
          border: '1px solid #f1f5f9',
          display: 'flex',
          flexDirection: 'column',
          gap: '1rem'
        }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <div style={{
                width: '40px',
                height: '40px',
                borderRadius: '12px',
                background: searchMeta.isInsured ? 'rgba(16, 185, 129, 0.1)' : 'rgba(245, 158, 11, 0.1)',
                display: 'flex',
                alignItems: 'center',
                justifyContent: 'center',
                color: searchMeta.isInsured ? '#10b981' : '#f59e0b'
              }}>
                {searchMeta.isInsured ? <Check size={20} /> : <AlertTriangle size={20} />}
              </div>
              <div>
                <h2 style={{ fontSize: '1.125rem', fontWeight: 700, margin: 0, color: '#1e293b' }}>
                  {searchMeta.isInsured ? 'Formulary Status: Covered' : 'Formulary Status: Not Covered'}
                </h2>
                <p style={{ margin: 0, fontSize: '0.875rem', color: '#64748b' }}>{summaryText}</p>
              </div>
            </div>
            {searchMeta.correctedDrugName && searchMeta.correctedDrugName !== searchMeta.searchedDrug && (
              <div style={{ fontSize: '0.8125rem', padding: '6px 12px', background: '#f8fafc', borderRadius: '8px', color: '#475569', border: '1px solid #e2e8f0' }}>
                Auto-corrected from: <strong>{searchMeta.searchedDrug}</strong>
              </div>
            )}
          </div>

          {searchMeta.message && (
            <div style={{
              fontSize: '0.875rem',
              color: '#475569',
              padding: '12px 16px',
              background: '#f8fafc',
              borderRadius: '12px',
              borderLeft: '4px solid var(--accent-color)'
            }}>
              {searchMeta.message}
            </div>
          )}
        </div>
      )}

      {/* Safest ML Recommendation Highlight */}
      {searchMeta.safestRecommendation && (
        <div style={{
          marginTop: '0.5rem',
          padding: '1.5rem',
          background: 'linear-gradient(135deg, #1e293b 0%, #0f172a 100%)',
          borderRadius: '20px',
          color: 'white',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          gap: '2rem',
          position: 'relative',
          overflow: 'hidden'
        }}>
          <div style={{ position: 'absolute', right: '-20px', top: '-20px', opacity: 0.1 }}>
            <Activity size={120} />
          </div>
          <div style={{ position: 'relative', zIndex: 1 }}>
            <span style={{
              fontSize: '0.75rem',
              fontWeight: 800,
              textTransform: 'uppercase',
              letterSpacing: '0.05em',
              background: 'var(--accent-color)',
              padding: '4px 10px',
              borderRadius: '6px',
              marginBottom: '12px',
              display: 'inline-block'
            }}>
              ML SAFETY RECOMMENDATION
            </span>
            <h3 style={{ fontSize: '1.5rem', fontWeight: 800, margin: '4px 0' }}>
              {searchMeta.safestRecommendation.name}
            </h3>
            <p style={{ margin: 0, fontSize: '0.875rem', color: '#94a3b8' }}>
              Verified as the safest alternative for this patient profile ({searchMeta.safestRecommendation.safety_score}% Safety Score).
            </p>
          </div>
          <div style={{ display: 'flex', gap: '12px', position: 'relative', zIndex: 1 }}>
            <button
              onClick={() => handleQuickView(searchMeta.safestRecommendation.name)}
              style={{
                padding: '10px 24px',
                borderRadius: '12px',
                background: 'white',
                color: '#0f172a',
                fontWeight: 700,
                border: 'none',
                cursor: 'pointer'
              }}
            >
              View Details
            </button>
          </div>
        </div>
      )}

      <div className="search-layout" style={{ marginTop: '2rem' }}>
        <aside className="filters-sidebar">
          <div style={{ marginBottom: '1.5rem', paddingBottom: '1.5rem', borderBottom: '1px solid #e2e8f0' }}>
            <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '1rem' }}>Search Optimization</h3>
            <button
              onClick={() => setExpandedForm(!expandedForm)}
              style={{
                width: '100%',
                padding: '10px',
                borderRadius: '10px',
                background: expandedForm ? '#f1f5f9' : 'white',
                border: '1px solid #e2e8f0',
                display: 'flex',
                alignItems: 'center',
                gap: '8px',
                fontSize: '0.875rem',
                fontWeight: 600,
                cursor: 'pointer'
              }}
            >
              <Activity size={16} />
              {expandedForm ? 'Hide Patient Profile' : 'Show Patient Profile'}
            </button>
          </div>

          {filterGroups.map((group) => (
            <div key={group.name} className="filter-section">
              <h3>
                {group.label}
                <span className="filter-toggle">▼</span>
              </h3>
              <ul className="filter-list">
                {group.options.map((opt) => (
                  <li key={opt.value} className="filter-item">
                    <label>
                      <input
                        type="checkbox"
                        value={opt.value}
                        checked={checkedFilters[group.name]?.includes(opt.value) || false}
                        onChange={(e) => handleFilterChange(group.name, opt.value, e.target.checked)}
                      />
                      {opt.label}
                    </label>
                  </li>
                ))}
              </ul>
            </div>
          ))}
        </aside>

        <div className="search-results">
          <div className="results-header">
            <div className="results-count" id="resultsCount">
              <span style={{ color: 'var(--accent-color)' }}>{results.length}</span> Results for{' '}
              <strong>"{query || 'All Drugs'}"</strong>
            </div>
            <div className="results-controls">
              <button
                className="filter-dropdown filter-btn"
                type="button"
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  gap: '8px',
                  padding: '10px 20px',
                  borderRadius: '12px',
                  border: '1px solid #e2e8f0',
                  background: '#ffffff',
                  color: '#475569',
                  fontSize: '0.875rem',
                  fontWeight: 700,
                  cursor: 'pointer',
                  transition: 'all 0.2s cubic-bezier(0.4, 0, 0.2, 1)',
                  boxShadow: '0 2px 4px rgba(15, 23, 42, 0.05)',
                  outline: 'none'
                }}
                onMouseOver={(e) => {
                  e.currentTarget.style.borderColor = '#16a085';
                  e.currentTarget.style.color = '#16a085';
                  e.currentTarget.style.boxShadow = '0 4px 12px rgba(22, 160, 133, 0.1)';
                }}
                onMouseOut={(e) => {
                  e.currentTarget.style.borderColor = '#e2e8f0';
                  e.currentTarget.style.color = '#475569';
                  e.currentTarget.style.boxShadow = '0 2px 4px rgba(15, 23, 42, 0.05)';
                }}
              >
                <SlidersHorizontal size={16} />
                All Filters
              </button>
            </div>
          </div>

          <div className="results-list" id="resultsList">
            {isLoading ? (
              <div className="loading-state">
                <div className="spinner"></div>
                <p>Analyzing formulary databases with RAG...</p>
              </div>
            ) : error ? (
              <div className="empty-state error-state">
                <div className="empty-state-icon">
                  <AlertTriangle size={48} />
                </div>
                <h3>Search Failed</h3>
                <p>{error}</p>
                <button className="btn-search" onClick={handleSearch}>Retry Search</button>
              </div>
            ) : pageData.length === 0 ? (
              <div className="empty-state">
                <div className="empty-state-icon">
                  <SearchIcon size={48} />
                </div>
                <h3>No medications found</h3>
                <p>Try a different drug name or select another insurance provider.</p>
              </div>
            ) : (
              <div className="search-rx-grid">
                {pageData
                  .filter(drug => !searchMeta.safestRecommendation || drug.safety_score === undefined || drug.safety_score >= 80)
                  .sort((a, b) => (b.safety_score || 0) - (a.safety_score || 0))
                  .map((drug, index) => (
                    <div
                      key={drug.id}
                      style={{
                        animation: `slideUpFade 0.4s ease-out forwards ${index * 0.1}s`,
                        opacity: 0,
                        transform: 'translateY(20px)'
                      }}
                    >
                      <DrugCard
                        drug={drug}
                        bookmarked={isBookmarked(drug.name)}
                        onView={handleQuickView}
                        onBookmark={toggleBookmark}
                      />
                    </div>
                  ))}
              </div>
            )}
          </div>

          {totalPages > 1 && (
            <div className="pagination" id="pagination">
              <button className="page-btn" onClick={() => changePage(currentPage - 1)} disabled={currentPage === 1}>
                ‹ Previous
              </button>
              {Array.from({ length: totalPages }, (_, index) => index + 1)
                .filter((page) => page === 1 || page === totalPages || (page >= currentPage - 2 && page <= currentPage + 2))
                .map((page, idx, arr) => (
                  <React.Fragment key={page}>
                    {idx > 0 && arr[idx - 1] !== page - 1 && <span className="page-btn">...</span>}
                    <button
                      className={`page-btn${page === currentPage ? ' active' : ''}`}
                      onClick={() => changePage(page)}
                    >
                      {page}
                    </button>
                  </React.Fragment>
                ))}
              <button className="page-btn" onClick={() => changePage(currentPage + 1)} disabled={currentPage === totalPages}>
                Next ›
              </button>
            </div>
          )}
        </div>
      </div>
      <QuickFormularyModal
        open={!!selectedModalDrug}
        drug={selectedModalDrug}
        onClose={() => setSelectedModalDrug(null)}
      />
    </div>
  );
};

export default Search;
