/* Shared employee sidebar toggle -- backs templates/_employee_sidebar.html. */
function toggleSidebar() {
  var sidebar = document.getElementById("sidebar");
  var overlay = document.getElementById("sbOverlay");
  if (!sidebar || !overlay) return;
  if (sidebar.classList.contains("open")) {
    sidebar.classList.remove("open");
    overlay.classList.remove("open");
  } else {
    sidebar.classList.add("open");
    overlay.classList.add("open");
  }
}
function closeSidebar() {
  var sidebar = document.getElementById("sidebar");
  var overlay = document.getElementById("sbOverlay");
  if (sidebar) sidebar.classList.remove("open");
  if (overlay) overlay.classList.remove("open");
}
