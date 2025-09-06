<!-- static/nav.js (yes, put it in JS, not HTML) -->
<script>
(async () => {
  // inject nav partial
  const mount = document.getElementById('site-nav');
  if (mount) {
    const html = await fetch('/static/partials/nav.html', {cache:'no-cache'}).then(r => r.text());
    mount.innerHTML = html;

    // theme toggle (simple)
    const btn = document.getElementById('themeToggle');
    if (btn) {
      btn.addEventListener('click', () => {
        const dark = document.documentElement.dataset.theme !== 'light';
        document.documentElement.dataset.theme = dark ? 'light' : 'dark';
      });
    }
  }
})();
</script>
