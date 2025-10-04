import { api } from './env.mjs';

async function ping() {
  const r = await fetch(api('/api/health'), { mode: 'cors' });
  const j = await r.json();
  document.querySelector('#out').textContent = JSON.stringify(j);
}
document.addEventListener('DOMContentLoaded', () =>
  document.querySelector('#ping').addEventListener('click', ping));















