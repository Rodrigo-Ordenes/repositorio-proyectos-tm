// Applied before the page paints so a chosen theme never flashes the other one. "auto" follows the system setting.
(function () {
  var theme = 'auto';
  try { theme = localStorage.getItem('theme') || 'auto'; } catch (e) {}
  if (theme === 'light' || theme === 'dark') document.documentElement.setAttribute('data-theme', theme);
})();
