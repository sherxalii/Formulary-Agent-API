const AUTH_KEY = 'mediformulary_auth';
const USER_KEY = 'mediformulary_user';
const TOKEN_KEY = 'mediformulary_token';
const BASE = import.meta.env.VITE_API_URL || 'http://localhost:8000/api';

export async function apiRequest(method, path, body = null, headers = {}) {
  const config = {
    method,
    headers: {
      'Content-Type': 'application/json',
      ...headers,
    },
    credentials: 'include', // Enable sending cookies
  };

  if (body) {
    config.body = JSON.stringify(body);
  }

  const response = await fetch(`${BASE}${path}`, config);
  const text = await response.text();
  try {
    const payload = JSON.parse(text);
    return { status: response.status, ok: response.ok, ...payload };
  } catch {
    return { status: response.status, ok: response.ok, raw: text };
  }
}

export const isAuthenticated = () => {
  return localStorage.getItem(AUTH_KEY) === 'true' && Boolean(localStorage.getItem(TOKEN_KEY));
};

export const getCurrentUser = () => {
  const raw = localStorage.getItem(USER_KEY);
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch {
    return null;
  }
};

export const getAuthToken = () => {
  return localStorage.getItem(TOKEN_KEY);
};

export const isAdmin = () => {
  const user = getCurrentUser();
  if (!user || !user.role) return false;
  const role = user.role.toLowerCase();
  return role === 'admin' || role === 'administrator';
};

export const loginUser = (user, token) => {
  localStorage.setItem(AUTH_KEY, 'true');
  localStorage.setItem(USER_KEY, JSON.stringify(user));
  localStorage.setItem(TOKEN_KEY, token);
  window.dispatchEvent(new Event('authChange'));
};

export const logoutUser = () => {
  localStorage.removeItem(AUTH_KEY);
  localStorage.removeItem(USER_KEY);
  localStorage.removeItem(TOKEN_KEY);
  window.dispatchEvent(new Event('authChange'));
};

export const updateUser = (updates) => {
  const current = getCurrentUser();
  if (!current) return null;
  const updated = { ...current, ...updates };
  localStorage.setItem(USER_KEY, JSON.stringify(updated));
  window.dispatchEvent(new Event('authChange'));
  return updated;
};

export const registerUserApi = async ({ name, email, password, role }) => {
  return apiRequest('POST', '/auth/register', { name, email, password, role });
};

export const loginUserApi = async ({ email, password }) => {
  return apiRequest('POST', '/auth/login', { email, password });
};

export const requestPasswordResetApi = async (email) => {
  return apiRequest('POST', '/auth/password-reset', { email });
};

export const confirmPasswordResetApi = async (token, password) => {
  return apiRequest('POST', '/auth/password-reset/confirm', { token, password });
};

export const changePasswordApi = async ({ email, current_password, new_password }) => {
  return apiRequest('POST', '/auth/password-change', {
    email,
    current_password,
    new_password,
  });
};

