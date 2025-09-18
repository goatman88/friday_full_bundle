<<<<<<< HEAD
import { Link, Routes, Route, Navigate } from 'react-router-dom'
import MultiUploader from './multi-uploader.jsx'
import CrawlUploader from './crawl-uploader.jsx'

const Nav = () => (
  <nav style={{display:'flex', gap:12, padding:12, borderBottom:'1px solid #eee'}}>
    <Link to="/multi-uploader">Multi Upload</Link>
    <Link to="/crawl-uploader">Single + Crawl</Link>
  </nav>
)

export default function App() {
  return (
    <div style={{maxWidth:920, margin:'0 auto', fontFamily:'system-ui, sans-serif'}}>
      <Nav />
      <Routes>
        <Route path="/" element={<Navigate to="/crawl-uploader" replace />} />
        <Route path="/multi-uploader" element={<MultiUploader />} />
        <Route path="/crawl-uploader" element={<CrawlUploader />} />
        <Route path="*" element={<div style={{padding:24}}>Not found</div>} />
      </Routes>
    </div>
  )
}
=======
import { useState } from 'react'
import reactLogo from './assets/react.svg'
import viteLogo from '/vite.svg'
import './App.css'

function App() {
  const [count, setCount] = useState(0)

  return (
    <>
      <div>
        <a href="https://vite.dev" target="_blank">
          <img src={viteLogo} className="logo" alt="Vite logo" />
        </a>
        <a href="https://react.dev" target="_blank">
          <img src={reactLogo} className="logo react" alt="React logo" />
        </a>
      </div>
      <h1>Vite + React</h1>
      <div className="card">
        <button onClick={() => setCount((count) => count + 1)}>
          count is {count}
        </button>
        <p>
          Edit <code>src/App.jsx</code> and save to test HMR
        </p>
      </div>
      <p className="read-the-docs">
        Click on the Vite and React logos to learn more
      </p>
    </>
  )
}

export default App
>>>>>>> ed49001 (Add Friday PowerShell client)
