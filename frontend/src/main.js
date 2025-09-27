import './style.css';

const el = document.querySelector('#app');
el.innerHTML = `
  <main>
    <h1>Hello Friday! 🎉</h1>
    <p>Your Vite app is running.</p>

    <form id="askForm">
      <input id="q" placeholder="Type something…" />
      <button>Ask</button>
    </form>
    <pre id="out"></pre>
  </main>
`;

document.querySelector('#askForm').addEventListener('submit', async (e) => {
  e.preventDefault();
  const q = document.querySelector('#q').value;
  try {
    const r = await fetch('http://localhost:8000/api/ask', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ q })
    });
    const data = await r.json();
    document.querySelector('#out').textContent = JSON.stringify(data, null, 2);
  } catch (err) {
    document.querySelector('#out').textContent = String(err);
  }
});








