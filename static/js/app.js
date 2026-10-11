/* Shared native form behavior; no frontend libraries. */
document.addEventListener('DOMContentLoaded', () => {
  document.querySelectorAll('[data-search-help]').forEach(button => {
    const panel = document.getElementById(button.getAttribute('aria-controls'));
    button.addEventListener('click', () => {
      panel.hidden = !panel.hidden;
      button.setAttribute('aria-expanded', String(!panel.hidden));
    });
    button.addEventListener('keydown', event => {
      if (event.key === 'Escape') { panel.hidden = true; button.setAttribute('aria-expanded', 'false'); }
    });
  });
  const token = document.querySelector('meta[name="csrf-token"]')?.content;
  document.querySelectorAll('[data-confirm]').forEach(button => {
    button.addEventListener('click', event => { if (!window.confirm(button.dataset.confirm)) event.preventDefault(); });
  });
  document.querySelectorAll('form[name="admin_editor"], form[name="submission_form"], .login-card form').forEach(form => {
    const status = document.createElement('p');
    status.setAttribute('role', 'status'); form.append(status);
    form.addEventListener('submit', async event => {
      event.preventDefault();
      const submit = form.querySelector('[type="submit"]');
      if (submit) submit.disabled = true;
      status.textContent = 'Saving…';
      try {
        const response = await fetch(window.location.pathname, { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': token }, body: new FormData(form) });
        const data = await response.json(); status.textContent = data.message;
        if (response.ok && data.status === 'success') {
          if (window.opener) { window.opener.location.reload(); window.close(); }
          else window.location.assign(form.dataset.successUrl || '/');
        }
      } catch (error) { status.textContent = 'Unable to reach the server. Please try again.'; }
      finally { if (submit) submit.disabled = false; }
    });
  });
});
