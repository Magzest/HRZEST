/* Retrofits ARIA roles/states and keyboard navigation onto an existing
 * click-driven tab strip, without touching its own activation logic.
 *
 * The caller (settings.html) keeps its switchGroup()/switchSub() functions
 * exactly as-is -- this only (a) stamps role/aria-* onto the tab buttons and
 * their panels once, and (b) adds a keydown listener that moves focus with
 * arrow keys and re-dispatches a click so the existing onclick handler does
 * the actual activation.
 */
(function () {
  function wireTabList(tabSelector, panelIdFor, opts) {
    opts = opts || {};
    var tabs = Array.prototype.slice.call(document.querySelectorAll(tabSelector));
    if (!tabs.length) return;

    var list = tabs[0].parentElement;
    if (list && !list.getAttribute('role')) list.setAttribute('role', 'tablist');

    tabs.forEach(function (tab) {
      tab.setAttribute('role', 'tab');
      tab.setAttribute('tabindex', tab.classList.contains('active') ? '0' : '-1');
      tab.setAttribute('aria-selected', tab.classList.contains('active') ? 'true' : 'false');
      var panelId = panelIdFor(tab);
      if (panelId) {
        tab.setAttribute('aria-controls', panelId);
        var panel = document.getElementById(panelId);
        if (panel) panel.setAttribute('role', 'tabpanel');
      }
      tab.addEventListener('keydown', function (e) {
        var idx = tabs.indexOf(tab);
        var next = null;
        if (e.key === 'ArrowRight' || e.key === 'ArrowDown') next = tabs[(idx + 1) % tabs.length];
        else if (e.key === 'ArrowLeft' || e.key === 'ArrowUp') next = tabs[(idx - 1 + tabs.length) % tabs.length];
        else if (e.key === 'Home') next = tabs[0];
        else if (e.key === 'End') next = tabs[tabs.length - 1];
        else if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault();
          tab.click();
          return;
        } else {
          return;
        }
        e.preventDefault();
        next.focus();
        next.click();
      });
    });

    if (opts.observe) {
      var mo = new MutationObserver(function () {
        tabs.forEach(function (tab) {
          var active = tab.classList.contains('active');
          tab.setAttribute('tabindex', active ? '0' : '-1');
          tab.setAttribute('aria-selected', active ? 'true' : 'false');
        });
      });
      tabs.forEach(function (tab) { mo.observe(tab, { attributes: true, attributeFilter: ['class'] }); });
    }
  }

  function wireDropdown(toggleSelector, menuSelector) {
    var toggles = document.querySelectorAll(toggleSelector);
    toggles.forEach(function (toggle) {
      var menu = toggle.parentElement ? toggle.parentElement.querySelector(menuSelector) : null;
      if (!menu) return;
      toggle.setAttribute('aria-haspopup', 'true');
      toggle.setAttribute('aria-expanded', 'false');
      var mo = new MutationObserver(function () {
        toggle.setAttribute('aria-expanded', menu.classList.contains('open') ? 'true' : 'false');
      });
      mo.observe(menu, { attributes: true, attributeFilter: ['class'] });
      toggle.addEventListener('keydown', function (e) {
        if (e.key === 'Escape' && menu.classList.contains('open')) {
          menu.classList.remove('open');
          toggle.focus();
        }
      });
    });
  }

  window.ezWireTabList = wireTabList;
  window.ezWireDropdown = wireDropdown;
})();
