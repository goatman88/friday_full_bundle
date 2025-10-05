import { VITE_BACKEND_URL } from './env.mjs';

async function ping() {
  const r = await fetch(\\/api/health\);
  const t = await r.text();
  document.body.innerHTML =
    '<h1>Friday Frontend</h1><button id="btn">Ping backend</button><pre>'+t+'</pre>';
}
document.addEventListener('click', e => { if(e.target.id==='btn') ping() });
ping();



