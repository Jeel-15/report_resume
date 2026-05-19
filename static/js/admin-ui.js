// Shared admin JS helpers: paged API, toast, delegation
(function(window){
  'use strict';

  const getToken = () => {
    const t = localStorage.getItem('token');
    if (!t) return null;
    return t;
  };

  async function apiPaged(path, opts = {}){
    // opts: { method, params: URLSearchParams|Object, body }
    const token = getToken();
    if (!token) throw new Error('no token');
    const params = opts.params instanceof URLSearchParams ? opts.params : new URLSearchParams(opts.params || {});
    const url = params.toString() ? `${path}?${params.toString()}` : path;
    const res = await fetch(url, {
      method: opts.method || 'GET',
      headers: Object.assign({ 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' }, opts.headers || {}),
      body: opts.body ? JSON.stringify(opts.body) : undefined
    });
    if (res.status === 401 || res.status === 403){
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/login';
      return null;
    }
    const data = await res.json().catch(() => null);
    if (!res.ok) throw new Error((data && data.message) || `Request failed: ${res.status}`);
    return data;
  }

  // Simple toast
  let _toastTimer = null;
  function showToast(msg, isError){
    let el = document.getElementById('adminSharedToast');
    if (!el){
      el = document.createElement('div'); el.id = 'adminSharedToast'; el.className = 'admin-toast'; document.body.appendChild(el);
    }
    el.textContent = msg || '';
    el.style.background = isError ? '#dc2626' : '';
    el.classList.add('show');
    if (_toastTimer) clearTimeout(_toastTimer);
    _toastTimer = setTimeout(()=> el.classList.remove('show'), 2200);
  }

  // delegated click utility
  function delegate(container, selector, handler){
    container = (typeof container === 'string') ? document.querySelector(container) : container;
    if (!container) return () => {};
    const listener = function(e){
      const target = e.target.closest && e.target.closest(selector);
      if (!target) return;
      handler.call(target, e, target);
    };
    container.addEventListener('click', listener);
    return () => container.removeEventListener('click', listener);
  }

  // expose
  window.AdminUI = window.AdminUI || {};
  window.AdminUI.apiPaged = apiPaged;
  window.AdminUI.showToast = showToast;
  window.AdminUI.delegate = delegate;

})(window);
