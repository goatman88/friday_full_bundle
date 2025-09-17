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
