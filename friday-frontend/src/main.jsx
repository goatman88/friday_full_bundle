// friday-frontend/src/main.jsx (or App.jsx)
import { getHealth, API_BASE } from './api';

getHealth()
  .then(() => (document.getElementById('health').textContent = 'ok'))
  .catch(() => (document.getElementById('health').textContent = 'error'));

document.getElementById('api').textContent = API_BASE;

