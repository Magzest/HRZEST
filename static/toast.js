// Toast Notification Engine
function showToast(message, type = 'info') {
  let container = document.getElementById('toast-container');
  if (!container) {
    container = document.createElement('div');
    container.id = 'toast-container';
    document.body.appendChild(container);
  }

  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  
  let iconHtml = '<i class="ti ti-info-circle"></i>';
  if (type === 'success') iconHtml = '<i class="ti ti-circle-check"></i>';
  if (type === 'error') iconHtml = '<i class="ti ti-alert-triangle"></i>';

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
