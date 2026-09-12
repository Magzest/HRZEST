// Toast Notification Engine -- single shared implementation for the whole
// app (admin_base.html's live-dashboard alerts, employee_portal.html,
// salary_report.html, and any window.alert() call on a page that loads
// this script -- see the override at the bottom of this file).
function showToast(message, type = 'info', icon = null) {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    // Toasts are injected after the page has already loaded/been read --
    // without this, a screen-reader user gets no announcement at all when
    // one appears. "polite" (not "assertive") queues the announcement
    // behind whatever the user is currently doing, rather than
    // interrupting it -- appropriate for a passive notification, not an
    // urgent one.
    container.setAttribute('role', 'status');
    container.setAttribute('aria-live', 'polite');
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;

  const defaultIcons = { success: 'circle-check', error: 'alert-triangle', alert: 'alert-triangle', info: 'info-circle' };
  const iconHtml = `<i class="ti ti-${icon || defaultIcons[type] || 'info-circle'}"></i>`;

  toast.innerHTML = `
    <div class="toast-icon">${iconHtml}</div>
    <div class="toast-content">${message}</div>
  `;

  container.appendChild(toast);
  
  // Trigger animation
  requestAnimationFrame(() => {
    toast.classList.add('show');
  });

  // Auto-remove
  setTimeout(() => {
    toast.classList.remove('show');
    toast.classList.add('hide');
    setTimeout(() => {
      toast.remove();
    }, 300); // Wait for transition
  }, 4000);
}

// Override native alert to use Toast for a better UI experience
window.alert = function(msg) {
  showToast(msg, 'info');
};
