import React from "react";
import { BrowserRouter, Routes, Route, Link } from "react-router-dom";
import MultiUploader from "./pages/MultiUploader";
import CrawlUpload from "./pages/CrawlUpload";

function Home(){
  const base = import.meta.env.VITE_API_BASE || "(same origin)";
  return (
    <div style={{maxWidth:720, margin:"40px auto", fontFamily:"system-ui, sans-serif"}}>
      <h1>Friday • Upload Tools</h1>
      <p>Backend: <code>{base}</code></p>
      <ul>
        <li><Link to="/multi-uploader">Multi-file Upload (S3 presign)</Link></li>
        <li><Link to="/crawl-upload">Single URL Crawl</Link></li>
      </ul>
    </div>
  );
}

export default function App(){
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Home/>}/>
        <Route path="/multi-uploader" element={<MultiUploader/>}/>
        <Route path="/crawl-upload" element={<CrawlUpload/>}/>
      </Routes>
    </BrowserRouter>
  );
}
