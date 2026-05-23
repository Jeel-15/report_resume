(function () {
  'use strict';

  const getToken = () => localStorage.getItem('token') || '';

  const authHeaders = (extra = {}) => {
    const token = getToken();
    return {
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...extra,
    };
  };

  const jsonHeaders = (extra = {}) => authHeaders({
    'Content-Type': 'application/json',
    ...extra,
  });

  const apiUrl = (path, params = {}, includeTokenQuery = false) => {
    const url = new URL(path, window.location.origin);
    if (includeTokenQuery) {
      const token = getToken();
      if (token) url.searchParams.set('token', token);
    }
    Object.entries(params || {}).forEach(([key, value]) => {
      if (value !== undefined && value !== null && value !== '') {
        url.searchParams.set(key, String(value));
      }
    });
    return url.toString();
  };

  const normalizeListResponse = (payload) => {
    if (Array.isArray(payload)) return payload;
    if (Array.isArray(payload?.items)) return payload.items;
    if (Array.isArray(payload?.data)) return payload.data;
    return [];
  };

  const showToast = (message, type = 'info', duration = 3000) => {
    if (typeof window.showToast === 'function') {
      window.showToast(message, type, duration);
      return;
    }
    if (message) {
      console.log(`[${type}] ${message}`);
    }
  };

  window.studentUI = {
    getToken,
    authHeaders,
    jsonHeaders,
    apiUrl,
    normalizeListResponse,
    showToast,
  };
})();