/**
 * Clinical AI Service
 * Handles AI responses, intent detection, and data integration
 */

const API_BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

// Intent detection
export const detectIntent = (query) => {
  const queryLower = query.toLowerCase();
  
  const patterns = {
    drugInfo: /^(what|how|tell|explain|info|about)\s+(is|are|the)?\s*(\w+)?|drug information/i,
    drugInteraction: /interact|interaction|with|together|combination|mix|concurrent/i,
    contraindication: /contraindicate|contraindication|cannot|should not|avoid|safe (for|with)/i,
    alternative: /alternative|instead|substitute|replacement|similar|equivalent/i,
    coverage: /cover|covered|insurance|formulary|plan|tier|cost|price|generic/i,
    dosage: /dose|dosage|how much|concentration|strength|mg|ml|frequency/i
  };

  for (const [intent, regex] of Object.entries(patterns)) {
    if (regex.test(queryLower)) {
      return intent;
    }
  }
  
  return 'general';
};

// Fetch drug information from backend
export const fetchDrugData = async (drugName) => {
  try {
    const response = await fetch(`${API_BASE}/drugs/${encodeURIComponent(drugName)}`);
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.error('Error fetching drug data:', error);
    return null;
  }
};

// Fetch insurance coverage
export const fetchCoverage = async (drugName) => {
  try {
    const response = await fetch(`${API_BASE}/formulary/check?drug=${encodeURIComponent(drugName)}`);
    if (!response.ok) return null;
    return await response.json();
  } catch (error) {
    console.error('Error fetching coverage:', error);
    return null;
  }
};

// Stream AI response from backend
export const streamAIResponse = async (query, drugData, coverageData, onChunk) => {
  try {
    const payload = {
      query,
      intent: detectIntent(query),
      drugData: drugData || {},
      coverageData: coverageData || {},
      timestamp: new Date().toISOString()
    };

    const response = await fetch(`${API_BASE}/ai/chat-stream`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Status ${response.status}`);
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let fullText = '';

    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      const chunk = decoder.decode(value, { stream: true });
      fullText += chunk;
      
      // Parse streaming format (assumes newline-delimited JSON or raw text)
      onChunk(chunk);
    }

    return fullText;
  } catch (error) {
    console.error('Streaming error:', error);
    throw error;
  }
};

// Fallback: Non-streaming response
export const getClinicalResponse = async (query, drugData, coverageData) => {
  try {
    const payload = {
      query,
      intent: detectIntent(query),
      drugData: drugData || {},
      coverageData: coverageData || {},
      timestamp: new Date().toISOString()
    };

    const response = await fetch(`${API_BASE}/ai/chat`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });

    if (!response.ok) {
      throw new Error(`Status ${response.status}`);
    }

    const data = await response.json();
    return data.response || data.message || 'Unable to process query';
  } catch (error) {
    console.error('Error getting clinical response:', error);
    throw error;
  }
};

// Cache for queries
const queryCache = new Map();

export const getCachedOrFetch = async (query) => {
  if (queryCache.has(query)) {
    return queryCache.get(query);
  }
  
  // Fetch fresh data
  const result = await getClinicalResponse(query);
  queryCache.set(query, result);
  
  // Limit cache size
  if (queryCache.size > 50) {
    const firstKey = queryCache.keys().next().value;
    queryCache.delete(firstKey);
  }
  
  return result;
};

// Parse structured response
export const parseStructuredResponse = (text) => {
  const sections = {
    overview: '',
    safety: [],
    coverage: '',
    alternatives: [],
    warnings: []
  };

  const lines = text.split('\n');
  let currentSection = 'overview';

  for (const line of lines) {
    if (line.includes('Safety') || line.includes('Side Effect')) {
      currentSection = 'safety';
    } else if (line.includes('Coverage') || line.includes('Insurance')) {
      currentSection = 'coverage';
    } else if (line.includes('Alternative') || line.includes('Substitute')) {
      currentSection = 'alternatives';
    } else if (line.includes('Warning') || line.includes('Contraindication') || line.includes('Caution')) {
      currentSection = 'warnings';
    } else if (line.trim()) {
      if (Array.isArray(sections[currentSection])) {
        sections[currentSection].push(line.trim());
      } else {
        sections[currentSection] += line + ' ';
      }
    }
  }

  return sections;
};
