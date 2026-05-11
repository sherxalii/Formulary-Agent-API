// CONFIGURATION OPTIONS:
// Direct connection to the FastAPI backend (preferred)
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// If needed, configure a custom backend URL in .env/VITE_API_URL

async function request(method, path, body, options = {}) {
  const config = {
    method,
    headers: { 
      'Content-Type': 'application/json',
      ...options.headers 
    },
    signal: options.signal,
  };
  
  if (body && !(body instanceof FormData)) {
    config.body = JSON.stringify(body);
  } else if (body instanceof FormData) {
    config.body = body;
    delete config.headers['Content-Type']; // let browser set multipart boundary
  }
  
  try {
    const res = await fetch(`${BASE}${path}`, config);
    const text = await res.text();
    try {
      const payload = JSON.parse(text);
      return { success: res.ok, ...payload };
    } catch {
      return { success: res.ok, raw: text };
    }
  } catch (error) {
    console.error(`API request failed to ${BASE}${path}:`, error);
    return { success: false, error: error.message };
  }
}

// ─── Health ──────────────────────────────────────────────────────────────────
export const checkHealth = () => request('GET', '/health');

// ─── Databases ───────────────────────────────────────────────────────────────
export const listDatabases = () => request('GET', '/databases');

// ─── RAG Formulary Search ────────────────────────────────────────────────────
/**
 * Search for formulary alternatives using the RAG AI engine.
 * @param {string} drugName - Brand or generic drug name
 * @param {string} insuranceName - Insurance/formulary database name
 * @param {string} [patientId='WEB001'] - Patient identifier
 */
/**
 * Search for formulary alternatives using the RAG AI engine.
 * @param {string} drugName - Brand or generic drug name
 * @param {string} insuranceName - Insurance/formulary database name
 * @param {string} [patientId='WEB001'] - Patient identifier
 * @param {object} [patientContext] - Optional runtime patient data
 */
export const getAlternatives = (drugName, insuranceName, patientId = 'WEB001', patientContext = null) =>
  request('POST', '/search', { 
    drug_name: drugName, 
    insurance_name: insuranceName, 
    patient_id: patientId,
    patient_context: patientContext
  });

export const getAutocomplete = (query) => request('GET', `/autocomplete?q=${encodeURIComponent(query)}`);


// ─── PDF Management ──────────────────────────────────────────────────────────
// ─── PDF & Database Management ──────────────────────────────────────────────
export const listPdfs = () => request('GET', '/list-pdfs');

/**
 * Get detailed status of all databases for management.
 */
export const getDatabaseStatus = () => request('GET', '/database-status');

/**
 * List all drugs extracted in a specific database.
 */
export const getDatabaseDrugs = (dbName) => request('GET', `/database/${encodeURIComponent(dbName)}/drugs`);

export const uploadPdf = (file) => {
  const form = new FormData();
  form.append('pdf', file);
  return request('POST', '/upload-pdf', form);
};

export const uploadFormulary = uploadPdf;

export const getEmbeddingStatus = (filename) => request('GET', `/embedding-status/${encodeURIComponent(filename)}`);

/**
 * Delete a database and its associated PDF.
 */
export const deleteDatabase = (dbName) => request('DELETE', `/database/${encodeURIComponent(dbName)}`);
export const deleteEmbedding = (filename) => request('DELETE', `/delete-embedding/${encodeURIComponent(filename)}`);

export const getViewPdfUrl = (filename) => `${BASE}/view-pdf/${encodeURIComponent(filename)}`;
export const getDownloadUrl = (filename) => `${BASE}/download-embedding/${encodeURIComponent(filename)}`;

/**
 * Comprehensive AI Search endpoint for drug information queries.
 * @param {string} query - The user's question or drug
 * @param {string} [insuranceName] - Optional insurance name for formulary context
 * @param {object} [patientContext] - Patient data (age, conditions, allergies)
 */
export const aiSearch = (query, insuranceName = '', patientContext = null) =>
  request('POST', '/ai-search', { 
      query, 
      insurance_plan: insuranceName,
      patient_context: patientContext || { age: 0, conditions: [], allergies: [] }
  });

// ─── Cache ───────────────────────────────────────────────────────────────────
export const getCacheStatus = () => request('GET', '/cache-status');
export const clearCache = () => request('POST', '/clear-cache');

// ─── Mediform AI - Clinical AI Assistant ──────────────────────────────────────
/**
 * Fetch comprehensive drug information for Mediform AI
 * @param {string} drugName - Drug name to fetch info for
 */
export const fetchMediformDrugData = (drugName) => 
  request('GET', `/drugs/${encodeURIComponent(drugName)}`);

/**
 * Check insurance coverage for a drug (Mediform AI)
 * @param {string} drugName - Drug name
 * @param {string} [planId] - Insurance plan ID
 */
export const checkFormularyCoverage = (drugName, planId = '') =>
  request('GET', `/formulary/check?drug=${encodeURIComponent(drugName)}${planId ? `&plan=${planId}` : ''}`);

/**
 * Stream clinical AI response from Mediform AI
 * WARNING: This returns a ReadableStream, handle in component with streaming code
 * @param {object} payload - { query, intent, drugData, coverageData, timestamp }
 */
export const streamMediformAIResponse = async (payload) => {
  const response = await fetch(`${BASE}/ai/chat-stream`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  
  if (!response.ok) {
    throw new Error(`API Error: ${response.status}`);
  }
  
  return response; // Returns response with body.getReader() for streaming
};

/**
 * Get non-streaming clinical AI response (fallback)
 * @param {object} payload - { query, intent, drugData, coverageData, timestamp }
 */
export const getMediformAIResponse = (payload) => 
  request('POST', '/ai/chat', payload);

/**
 * Perform a clinical safety check using ML models.
 * @param {string} drugName - The drug to check
 * @param {string} patientId - The patient ID (optional)
 */
export const checkDrugSafety = (drugName, patientId = 'WEB001') =>
  request('POST', '/safety-check', { drug_name: drugName, patient_id: patientId });

