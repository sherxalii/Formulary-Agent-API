import React, { useState, useEffect } from 'react';
import { Search, Plus, Trash2, AlertTriangle, ShieldCheck, Info, ArrowRight, Zap } from 'lucide-react';
import { apiRequest } from '../utils/auth';

const DDI = () => {
  const [searchTerm, setSearchTerm] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [selectedDrugs, setSelectedDrugs] = useState([]);
  const [interactions, setInteractions] = useState([]);
  const [loading, setLoading] = useState(false);
  const [isSearching, setIsSearching] = useState(false);

  // Mock search results for demonstration if API fails or for speed
  const performSearch = async (term) => {
    if (term.length < 2) {
      setSearchResults([]);
      return;
    }
    setIsSearching(true);
    try {
      // Use the independent RxNorm search for DDI
      const res = await apiRequest('GET', `/ddi/search?q=${term}`);
      if (res.success) {
        setSearchResults(res.results);
      }
    } catch (error) {
      console.error('Search failed', error);
    } finally {
      setIsSearching(false);
    }
  };

  useEffect(() => {
    const delayDebounceFn = setTimeout(() => {
      if (searchTerm) performSearch(searchTerm);
    }, 300);

    return () => clearTimeout(delayDebounceFn);
  }, [searchTerm]);

  const addDrug = (drug) => {
    if (!selectedDrugs.find(d => d.name === drug.name)) {
      setSelectedDrugs([...selectedDrugs, drug]);
    }
    setSearchTerm('');
    setSearchResults([]);
  };

  const removeDrug = (name) => {
    setSelectedDrugs(selectedDrugs.filter(d => d.name !== name));
  };

  const checkInteractions = async () => {
    if (selectedDrugs.length < 2) return;
    setLoading(true);
    try {
      const response = await apiRequest('POST', '/personalized-check', {
        drugs: selectedDrugs.map(d => ({ 
          drug_name: d.name, 
          rxcui: d.rxcui 
        })),
        patient_context: {
          conditions: [],
          allergies: [],
          medications: []
        }
      });
      
      if (response.success) {
        // Extract DDI alerts from the results
        const allAlerts = [];
        response.results.forEach(res => {
          res.alerts.forEach(alert => {
            if (alert.type === 'ddi') {
              // Avoid duplicates
              const alertKey = `${alert.message}-${alert.drugs.sort().join(',')}`;
              if (!allAlerts.find(a => a.key === alertKey)) {
                allAlerts.push({ ...alert, key: alertKey });
              }
            }
          });
        });
        setInteractions(allAlerts);
      }
    } catch (error) {
      console.error('DDI check failed', error);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="ddi-root">
      <div className="ddi-header">
        <div className="ddi-badge">Clinical Safety Tool</div>
        <h1>Drug Interaction <em>Checker</em></h1>
        <p>Check for potential interactions between multiple medications, including OTC drugs and supplements.</p>
      </div>

      <div className="ddi-container">
        <div className="ddi-main">
          {/* Search Section */}
          <div className="ddi-card ddi-search-card">
            <div className="ddi-card-title">
              <Plus size={20} /> Add Medications
            </div>
            <div className="ddi-search-box">
              <Search className="search-icon" size={20} />
              <input
                type="text"
                placeholder="Search global database (e.g. Aspirin, Warfarin...)"
                value={searchTerm}
                onChange={(e) => setSearchTerm(e.target.value)}
              />
              {isSearching && <div className="ddi-spinner-sm"></div>}
            </div>
            
            {searchResults.length > 0 && (
              <div className="ddi-results-dropdown">
                {searchResults.map((drug, idx) => (
                  <div key={idx} className="ddi-result-item" onClick={() => addDrug(drug)}>
                    <div className="result-icon"><ArrowRight size={14} /></div>
                    <div className="result-info">
                      <div className="result-name">{drug.name}</div>
                      <div className="result-meta">
                        {drug.rxcui ? `RXCUI: ${drug.rxcui}` : drug.availability}
                      </div>
                    </div>
                  </div>
                ))}
              </div>
            )}

            <div className="ddi-selected-list">
              {selectedDrugs.length === 0 ? (
                <div className="ddi-empty-state">
                  <Info size={32} />
                  <p>No medications added yet. Search and add at least two to check for interactions.</p>
                </div>
              ) : (
                selectedDrugs.map((drug, idx) => (
                  <div key={idx} className="ddi-selected-item">
                    <div className="item-content">
                      <div className="item-name">{drug.name}</div>
                      <div className="item-meta">{drug.rxcui ? `RXCUI: ${drug.rxcui}` : 'Medication'}</div>
                    </div>
                    <button className="item-remove" onClick={() => removeDrug(drug.name)}>
                      <Trash2 size={16} />
                    </button>
                  </div>
                ))
              )}
            </div>

            <button 
              className={`ddi-check-btn ${selectedDrugs.length < 2 ? 'disabled' : ''}`}
              onClick={checkInteractions}
              disabled={selectedDrugs.length < 2 || loading}
            >
              {loading ? 'Analyzing...' : 'Check for Interactions'}
              {!loading && <Zap size={18} />}
            </button>
          </div>
        </div>

        <div className="ddi-sidebar">
          {/* Results Section */}
          <div className="ddi-card ddi-results-card">
            <div className="ddi-card-title">
              <Zap size={20} /> Analysis Report
            </div>
            
            {loading ? (
              <div className="ddi-loading-state">
                <div className="ddi-spinner"></div>
                <p>Running clinical cross-reference...</p>
              </div>
            ) : interactions.length > 0 ? (
              <div className="ddi-interaction-list">
                <div className="ddi-count-badge major">
                  {interactions.length} Interaction{interactions.length > 1 ? 's' : ''} Found
                </div>
                {interactions.map((alert, idx) => (
                  <div key={idx} className={`ddi-alert-card ${alert.severity}`}>
                    <div className="alert-header">
                      <AlertTriangle size={18} />
                      <span>{alert.severity.toUpperCase()} INTERACTION</span>
                    </div>
                    <div className="alert-msg">{alert.message}</div>
                    <div className="alert-drugs">
                      {alert.drugs.join(' + ')}
                    </div>
                  </div>
                ))}
              </div>
            ) : selectedDrugs.length >= 2 ? (
              <div className="ddi-safe-state">
                <ShieldCheck size={48} color="#10b981" />
                <h3>No Interactions Found</h3>
                <p>Based on our current database, no significant interactions were found between the selected drugs.</p>
                <div className="ddi-disclaimer">
                  * Clinical data is updated regularly. Always consult with a healthcare professional before starting or changing medications.
                </div>
              </div>
            ) : (
              <div className="ddi-placeholder-state">
                <p>Your results will appear here after analysis.</p>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};

export default DDI;
