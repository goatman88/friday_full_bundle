import { api } from './env.mjs';

const $ = (sel) => document.querySelector(sel);

async function getJSON(url, opts) {
  const res = await fetch(url, { ...opts, mode: 'cors' });
  if (!res.ok) throw new Error(`HTTP ${res.status}`);
  return res.json();
}

async function ping() {
  try {
    const data = await getJSON(api('/api/health'));
    $('#out').textContent = JSON.stringify(data);
  } catch (e) {
    $('#out').textContent = `Error: ${e.message}`;
  }
}

window.addEventListener('DOMContentLoaded', () => {
  $('#ping').addEventListener('click', ping);
  // Optional: ping on load to show status
  // ping();
});














