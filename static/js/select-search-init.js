/*
  Global searchable dropdown behavior:
  - Keeps native select closed look
  - Shows search box only when dropdown is opened
  - Auto-applies to large option lists
*/
(function () {
  const MIN_OPTIONS_FOR_SEARCH = 8;
  const SKIP_ATTR = 'data-no-search';

  function isVisible(el) {
    if (!el) return false;
    return !!(el.offsetWidth || el.offsetHeight || el.getClientRects().length);
  }

  function isEligibleSelect(el) {
    if (!el || el.tagName !== 'SELECT') return false;
    if (el.disabled) return false;
    if (el.hasAttribute(SKIP_ATTR)) return false;
    if (el.multiple) return false;

    const searchableCount = Array.from(el.options || []).filter((opt) => {
      if (opt.disabled) return false;
      const value = String(opt.value || '').trim();
      const text = String(opt.textContent || '').trim();
      if (!value && !text) return false;
      if (!value) return false; // skip placeholders
      return true;
    }).length;

    return searchableCount >= MIN_OPTIONS_FOR_SEARCH;
  }

  function getSelect2Config(selectEl) {
    const config = {
      width: '100%',
      minimumResultsForSearch: 0,
      placeholder: selectEl.getAttribute('data-placeholder') || undefined,
    };

    const modal = selectEl.closest('.modal');
    if (modal) {
      config.dropdownParent = window.jQuery(modal);
    }

    return config;
  }

  function isEnhanced($select) {
    return $select.hasClass('select2-hidden-accessible');
  }

  function enhanceSelect(selectEl) {
    const $select = window.jQuery(selectEl);

    if (!isEligibleSelect(selectEl)) {
      if (isEnhanced($select)) {
        $select.select2('destroy');
      }
      return;
    }

    // Avoid initializing while hidden (tabs/accordions), because width calc can break.
    if (!isVisible(selectEl) && !isEnhanced($select)) {
      return;
    }

    if (isEnhanced($select)) {
      $select.trigger('change.select2');
      return;
    }

    $select.select2(getSelect2Config(selectEl));
  }

  function refreshAll(root) {
    const context = root && root.querySelectorAll ? root : document;
    const selects = context.querySelectorAll('select');
    selects.forEach(enhanceSelect);
  }

  function initObserver() {
    const observer = new MutationObserver((mutations) => {
      let fullRefreshNeeded = false;

      mutations.forEach((mutation) => {
        if (mutation.type !== 'childList') return;

        if (mutation.target && mutation.target.tagName === 'SELECT') {
          enhanceSelect(mutation.target);
        }

        mutation.addedNodes.forEach((node) => {
          if (node.nodeType !== 1) return;
          if (node.tagName === 'SELECT') {
            enhanceSelect(node);
            return;
          }
          if (node.querySelector && node.querySelector('select')) {
            fullRefreshNeeded = true;
          }
        });
      });

      if (fullRefreshNeeded) {
        refreshAll(document);
      }
    });

    observer.observe(document.body, {
      childList: true,
      subtree: true,
    });
  }

  function init() {
    if (!window.jQuery || !window.jQuery.fn || !window.jQuery.fn.select2) {
      return;
    }

    refreshAll(document);
    initObserver();

    // Lazy-init on first interaction for elements that were hidden at initial render.
    document.addEventListener('focusin', (event) => {
      const target = event.target;
      if (target && target.tagName === 'SELECT') {
        enhanceSelect(target);
      }
    });

    // Re-check when Bootstrap reveals hidden UI blocks.
    document.addEventListener('shown.bs.tab', () => refreshAll(document));
    document.addEventListener('shown.bs.collapse', () => refreshAll(document));
    document.addEventListener('shown.bs.modal', () => refreshAll(document));
  }

  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
