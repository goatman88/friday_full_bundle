import React, { useState } from "react";
import { api } from "../lib/api";

export default function CrawlUpload(){
  const [url, setUrl] = useState("");
  const [title, setTitle] = useState("");
  const [ext, setExt] = useState("crawl_" + Date.now());
  const [status, setStatus] = useState("");

  const submit = async (e)=>{
    e.preventDefault();
    setStatus("Submitting…");
    try{
      await api.indexUrl({ url, title: title || url, external_id: ext });
      setStatus("Queued for parsing/indexing ✅");
    }catch(err){
      setStatus("Error: " + String(err));
    }
  };

  return (
    <div style={{maxWidth:720, margin:"40px auto", fontFamily:"system-ui, sans-serif"}}>
      <h1>Single URL Crawl</h1>
      <form onSubmit={submit} style={{display:"grid", gap:12}}>
        <label>URL <input value={url} onChange={e=>setUrl(e.target.value)} placeholder="https://example.com/article" required style={{width:"100%"}}/></label>
        <label>Title (optional) <input value={title} onChange={e=>setTitle(e.target.value)} style={{width:"100%"}}/></label>
        <label>External ID <input value={ext} onChange={e=>setExt(e.target.value)} style={{width:"100%"}}/></label>
        <div>
          <button type="submit" style={{padding:"8px 14px", borderRadius:8, border:"1px solid #ddd", background:"#4f46e5", color:"#fff"}}>Submit</button>
        </div>
      </form>
      {status && <p style={{marginTop:12}}>{status}</p>}
    </div>
  );
}
