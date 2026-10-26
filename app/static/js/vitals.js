import {onCLS, onINP, onLCP} from '../vendor/web-vitals.js';

const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
const page = document.querySelector('meta[name="telemetry-page"]')?.content;
const pages = new Set(['main.dashboard', 'tickets.index', 'tickets.detail', 'tickets.create', 'auth.account']);

if (csrf && pages.has(page)) {
  const report = ({name, value}) => {
    fetch('/telemetry/vitals', {
      method: 'POST',
      headers: {'Content-Type': 'application/json', 'X-CSRFToken': csrf},
      credentials: 'same-origin',
      keepalive: true,
      body: JSON.stringify({name, value, page})
    }).catch(() => {});
  };
  onCLS(report);
  onINP(report);
  onLCP(report);
}
