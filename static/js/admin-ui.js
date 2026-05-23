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

  function normalizeListResponse(data){
    if (Array.isArray(data)){
      return {
        items: data,
        total: data.length,
        limit: null,
        offset: 0,
        raw: data,
      };
    }

    const payload = data && typeof data === 'object' ? data : {};
    const items = Array.isArray(payload.items) ? payload.items : [];
    const total = Number.isFinite(Number(payload.total)) ? Number(payload.total) : items.length;
    const limit = payload.limit !== undefined && payload.limit !== null && payload.limit !== ''
      ? Number(payload.limit)
      : null;
    const offset = payload.offset !== undefined && payload.offset !== null && payload.offset !== ''
      ? Number(payload.offset)
      : 0;

    return {
      items,
      total,
      limit: Number.isFinite(limit) ? limit : null,
      offset: Number.isFinite(offset) ? offset : 0,
      raw: payload,
    };
  }

  function setListFoot(footEl, total, page, pageSize, emptyText){
    if (!footEl) return;

    const safePageSize = Math.max(1, Number(pageSize) || 1);
    const totalCount = Math.max(0, Number(total) || 0);
    const currentPage = Math.max(1, Number(page) || 1);

    if (!totalCount){
      footEl.textContent = emptyText || 'No items found';
      return;
    }

    const start = ((currentPage - 1) * safePageSize) + 1;
    const end = Math.min(currentPage * safePageSize, totalCount);
    footEl.textContent = `Showing ${start}-${end} of ${totalCount.toLocaleString('en-IN')}`;
  }

  function setPagerState(pager, total, page){
    if (!pager || typeof pager.setTotal !== 'function') return;
    pager.setTotal(total, page);
  }

  // Simple toast
  let _toastTimer = null;
  function showToast(msg, type){
    let el = document.getElementById('adminSharedToast');
    if (!el){
      el = document.createElement('div'); el.id = 'adminSharedToast'; el.className = 'admin-toast'; document.body.appendChild(el);
    }
    el.textContent = msg || '';
    const tone = type === 'error' ? '#dc2626' : (type === 'warning' ? '#d97706' : (type === 'info' ? '#2563eb' : '#059669'));
    el.style.background = tone;
    el.classList.add('show');
    if (_toastTimer) clearTimeout(_toastTimer);
    _toastTimer = setTimeout(()=> el.classList.remove('show'), 2200);
  }

  function showBulkConfirm(count, entityLabel){
    return new Promise(function(resolve){
      const existing = document.getElementById('_bulkConfirmBar');
      if (existing) existing.remove();

      const label = entityLabel || 'items';
      const bar = document.createElement('div');
      bar.id = '_bulkConfirmBar';
      bar.style.cssText = [
        'position:fixed', 'bottom:24px', 'left:50%', 'transform:translateX(-50%)',
        'background:#1e293b', 'color:#fff', 'padding:14px 20px', 'border-radius:12px',
        'font-size:13px', 'z-index:9999', 'display:flex', 'gap:12px', 'align-items:center',
        'box-shadow:0 8px 32px rgba(0,0,0,0.3)'
      ].join(';');
      bar.innerHTML = [
        '<span>Delete <strong>' + count + '</strong> ' + label + '? This cannot be undone.</span>',
        '<button id="_bulkYes" style="padding:7px 18px;background:#dc2626;color:#fff;border:none;border-radius:8px;font-size:13px;font-weight:700;cursor:pointer;">Delete</button>',
        '<button id="_bulkNo" style="padding:7px 14px;background:transparent;border:1px solid rgba(255,255,255,0.3);color:#fff;border-radius:8px;font-size:13px;cursor:pointer;">Cancel</button>'
      ].join('');
      document.body.appendChild(bar);

      function cleanup(result) {
        bar.remove();
        resolve(result);
      }

      document.getElementById('_bulkYes').onclick = function () { cleanup(true); };
      document.getElementById('_bulkNo').onclick  = function () { cleanup(false); };
      setTimeout(function () { if (document.getElementById('_bulkConfirmBar')) cleanup(false); }, 12000);
    });
  }

  function initBulkSelect(opts){
    opts = opts || {};
    const selectAll = document.getElementById(opts.selectAllId || 'selectAll');
    const tbody = document.getElementById(opts.tbodyId || 'rows');
    const toolbar = document.getElementById(opts.toolbarId || 'bulkToolbar');
    const countEl = document.getElementById(opts.countId || 'selectedCount');
    const cbClass = opts.checkboxClass || 'row-checkbox';

    function getChecked(){
      return Array.from(document.querySelectorAll('.' + cbClass + ':checked'));
    }

    function updateToolbar(){
      const checked = getChecked();
      const all = document.querySelectorAll('.' + cbClass);
      if (toolbar) toolbar.classList.toggle('show', checked.length > 0);
      if (countEl) countEl.textContent = checked.length + ' selected';
      if (selectAll){
        selectAll.checked = all.length > 0 && checked.length === all.length;
        selectAll.indeterminate = checked.length > 0 && checked.length < all.length;
      }
    }

    function clearSelection(){
      document.querySelectorAll('.' + cbClass).forEach(function (cb) { cb.checked = false; });
      if (selectAll) { selectAll.checked = false; selectAll.indeterminate = false; }
      if (toolbar) toolbar.classList.remove('show');
      if (countEl) countEl.textContent = '0 selected';
    }

    function getSelectedIds(){
      return getChecked().map(function (cb) { return cb.dataset.id; });
    }

    if (selectAll){
      selectAll.addEventListener('change', function(){
        document.querySelectorAll('.' + cbClass).forEach(function(cb){
          cb.checked = selectAll.checked;
        });
        updateToolbar();
      });
    }

    if (tbody){
      tbody.addEventListener('change', function(e){
        if (e.target.classList.contains(cbClass)) updateToolbar();
      });
    }

    return { getSelectedIds: getSelectedIds, clearSelection: clearSelection, updateToolbar: updateToolbar };
  }

  function initPager(opts){
    opts = opts || {};
    const prevBtn = document.getElementById(opts.prevId);
    const nextBtn = document.getElementById(opts.nextId);
    const footEl = document.getElementById(opts.footId);
    const pageSize = opts.pageSize || 25;
    let _page = 1;
    let _total = 0;

    function setTotal(total, page){
      _total = total || 0;
      _page = page || _page;
      const totalPages = Math.max(1, Math.ceil(_total / pageSize));
      _page = Math.max(1, Math.min(totalPages, _page));

      if (prevBtn) prevBtn.disabled = _page <= 1;
      if (nextBtn) nextBtn.disabled = _page >= totalPages;

      if (footEl){
        const start = _total === 0 ? 0 : ((_page - 1) * pageSize) + 1;
        const end = Math.min(_page * pageSize, _total);
        footEl.textContent = _total === 0 ? 'No items found' : 'Showing ' + start + '–' + end + ' of ' + _total.toLocaleString('en-IN');
      }
    }

    if (prevBtn){
      prevBtn.addEventListener('click', function(){
        if (_page > 1){ _page -= 1; if (opts.onPage) opts.onPage(_page); }
      });
    }
    if (nextBtn){
      nextBtn.addEventListener('click', function(){
        const totalPages = Math.max(1, Math.ceil(_total / pageSize));
        if (_page < totalPages){ _page += 1; if (opts.onPage) opts.onPage(_page); }
      });
    }

    return { setTotal: setTotal, get currentPage(){ return _page; }, set currentPage(v){ _page = v; } };
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
  window.AdminUI.normalizeListResponse = normalizeListResponse;
  window.AdminUI.setListFoot = setListFoot;
  window.AdminUI.setPagerState = setPagerState;
  window.AdminUI.showToast = showToast;
  window.AdminUI.showBulkConfirm = showBulkConfirm;
  window.AdminUI.initBulkSelect = initBulkSelect;
  window.AdminUI.initPager = initPager;
  window.AdminUI.delegate = delegate;

  window.showToast = showToast;
  window.showBulkConfirm = showBulkConfirm;
  window.initBulkSelect = initBulkSelect;
  window.initPager = initPager;

})(window);
