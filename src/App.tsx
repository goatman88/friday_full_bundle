import { useState } from 'react';
import { pingBoth } from './api';

import MultiUploader from "./pages/MultiUploader.jsx";

function Home() {
  const [count, setCount] = useState(0);
  return (
    <div style={{maxWidth: 900, margin: "40px auto", padding: "0 16px", fontFamily: "system-ui, sans-serif"}}>
      <h1>Vite + React</h1>
      <p>Count is {count}</p>
      <button onClick={() => setCount(c => c + 1)}>Increment</button>

      <hr style={{margin:"24px 0"}} />
      <h3>Playground</h3>
      <ul>
        <li><Link to="/multi-uploader">Multi Uploader</Link></li>
      </ul>
    </div>
  );
}
function App() {
  const [result, setResult] = useState<string>('(click to test)');

  async function testBackend() {
    try {
      const data = await pingBoth();
      setResult(JSON.stringify(data));
    } catch (e: any) {
      setResult(`Error: ${e.message || e}`);
    }
  }

  return (
    <>
      <button onClick={testBackend}>Test backend /health + /api/health</button>
      <pre>{result}</pre>

      {/* ...rest of your UI... */}
    </>
  );
}

export default function App() {
  return (
    <Routes>
      <Route path="/" element={<Home />} />
      <Route path="/multi-uploader" element={<MultiUploader />} />
    </Routes>
  );
}

