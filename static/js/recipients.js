/* Resolve names and IDs without exposing the full account directory. */
document.addEventListener('DOMContentLoaded', () => {
  const input = document.getElementById('receiver_id');
  const results = document.getElementById('recipient-results');
  const status = document.getElementById('recipient-status');
  if (!input || !results || !status) return;
  let timer, controller, revision = 0;
  input.addEventListener('input', () => {
    clearTimeout(timer);
    controller?.abort();
    const current = ++revision;
    const keyword = input.value.trim();
    results.replaceChildren(); results.hidden = true;
    status.textContent = keyword ? 'Looking up recipient…' : '';
    input.setCustomValidity(keyword ? 'Select a matching recipient or enter a valid personal ID.' : '');
    if (!keyword) return;
    timer = setTimeout(async () => {
      controller = new AbortController();
      try {
        const response = await fetch('/messages/recipients?q=' + encodeURIComponent(keyword), { credentials: 'same-origin', signal: controller.signal });
        const data = await response.json();
        if (current !== revision) return;
        if (!response.ok) throw new Error(data.message || 'Unable to look up recipients.');
        if (!data.users.length) { status.textContent = 'No matching recipient found.'; return; }
        if (/^[0-9]+$/.test(keyword)) {
          input.value = String(data.users[0].id); input.setCustomValidity('');
          status.textContent = `${data.users[0].name} · Personal ID: ${data.users[0].id}`;
          return;
        }
        status.textContent = data.has_more ? 'More than 20 matches. Refine the name or select a recipient.' : 'Select the intended recipient below.';
        for (const user of data.users) {
          const button = document.createElement('button');
          button.type = 'button'; button.className = 'recipient-option';
          button.textContent = `${user.name} · ID ${user.id}`;
          button.addEventListener('click', () => {
            ++revision; controller?.abort();
            input.value = String(user.id); input.setCustomValidity('');
            status.textContent = `${user.name} · Personal ID: ${user.id}`;
            results.replaceChildren(); results.hidden = true; input.focus();
          });
          results.append(button);
        }
        results.hidden = false;
      } catch (error) {
        if (error.name !== 'AbortError' && current === revision) status.textContent = 'Unable to look up recipients. Please try again.';
      }
    }, 250);
  });
});
