import React, {useCallback, useMemo, useRef, useState} from "react";
import { api } from "../lib/api";

function prettyBytes(n){
  if(!Number.isFinite(n)) return "";
  const u=["B","KB","MB","GB"]; let i=0;
  while(n>=1024 && i<u.length-1){ n/=1024; i++; }
  return `${n.toFixed(n<10&&i>0?1:0)} ${u[i]}`;
}

export default function MultiUploader(){
  const [files, setFiles] = useState([]);               // [{file, status, pct, err, s3_uri}]
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef(null);

  const onPick = (list) => {
    const items = Array.from(list || []).map(f => ({
      file: f, status: "ready", pct: 0, err: "", s3_uri: ""
    }));
    setFiles(prev => [...prev, ...items]);
  };

  const onDrop = useCallback((e)=>{
    e.preventDefault();
    setDragOver(false);
    if (e.dataTransfer?.files?.length) onPick(e.dataTransfer.files);
  },[]);

  const onClickChoose = ()=> inputRef.current?.click();

  const uploadOne = async (idx) => {
    const it = files[idx]; if(!it) return;
    const f = it.file;
    const update = (patch)=> setFiles(arr=>{
      const clone = [...arr]; clone[idx] = {...clone[idx], ...patch}; return clone;
    });

    try{
      update({status:"presigning", pct:5, err:""});
      const { put_url, s3_uri } = await api.presign({ filename: f.name, content_type: f.type || "application/octet-stream" });

      update({status:"uploading", pct:15});
      await new Promise((resolve, reject)=>{
        const xhr = new XMLHttpRequest();
        xhr.open("PUT", put_url);
        xhr.setRequestHeader("Content-Type", f.type || "application/octet-stream");
        xhr.upload.onprogress = (e)=>{
          if(e.lengthComputable){
            const pct = 15 + Math.round((e.loaded/e.total)*70);
            update({pct});
          }
        };
        xhr.onload = ()=> xhr.status >= 200 && xhr.status < 300 ? resolve() : reject(new Error(`PUT ${xhr.status}`));
        xhr.onerror = ()=> reject(new Error("Network error"));
        xhr.send(f);
      });

      update({status:"confirming", pct:95});
      await api.confirm({
        s3_uri,
        title: f.name,
        external_id: `file_${Date.now()}_${idx}`,
        content: ""  // optional: extra text metadata for your indexer
      });

      update({status:"done", pct:100, s3_uri});
    }catch(err){
      update({status:"error", err:String(err)});
    }
  };

  const uploadAll = async ()=>{
    for(let i=0;i<files.length;i++){
      const it = files[i];
      if(it.status==="ready" || it.status==="error"){
        // eslint-disable-next-line no-await-in-loop
        await uploadOne(i);
      }
    }
  };

  const anyUploading = useMemo(()=> files.some(f=>["presigning","uploading","confirming"].includes(f.status)),[files]);

  return (
    <div style={{maxWidth:900, margin:"40px auto", fontFamily:"system-ui, sans-serif"}}>
      <h1>Multi-file Upload</h1>
      <p>
        Backend: <code>{import.meta.env.VITE_API_BASE || "(same origin)"}</code>
      </p>

      <div
        onDragOver={(e)=>{e.preventDefault(); setDragOver(true);}}
        onDragLeave={()=>setDragOver(false)}
        onDrop={onDrop}
        onClick={onClickChoose}
        style={{
          border:"2px dashed #888",
          borderColor: dragOver? "#4f46e5" : "#888",
          padding:"40px",
          borderRadius:12,
          textAlign:"center",
          cursor:"pointer",
          background: dragOver? "#eef2ff":"transparent"
        }}
        role="button"
        tabIndex={0}
      >
        <strong>Drag & drop</strong> files here or <u>click to choose</u>
        <input
          ref={inputRef}
          type="file"
          multiple
          onChange={(e)=> onPick(e.target.files)}
          style={{display:"none"}}
        />
      </div>

      {files.length>0 && (
        <>
          <div style={{display:"flex", justifyContent:"space-between", marginTop:20}}>
            <div>{files.length} file(s) queued</div>
            <div>
              <button
                onClick={uploadAll}
                disabled={anyUploading}
                style={{padding:"8px 14px", borderRadius:8, border:"1px solid #ddd", background:"#4f46e5", color:"#fff"}}
              >
                {anyUploading ? "Uploading…" : "Start upload"}
              </button>
            </div>
          </div>

          <ul style={{listStyle:"none", padding:0, marginTop:16}}>
            {files.map((it, i)=>(
              <li key={i} style={{padding:"10px 0", borderBottom:"1px solid #eee"}}>
                <div style={{display:"flex", gap:12, alignItems:"center", justifyContent:"space-between"}}>
                  <div style={{minWidth:0, flex:1}}>
                    <div style={{fontWeight:600, overflow:"hidden", textOverflow:"ellipsis", whiteSpace:"nowrap"}}>{it.file.name}</div>
                    <div style={{fontSize:12, color:"#666"}}>
                      {prettyBytes(it.file.size)} · {it.file.type || "application/octet-stream"}
                    </div>
                  </div>
                  <div style={{width:240}}>
                    <div style={{height:8, background:"#eee", borderRadius:999}}>
                      <div style={{height:8, background:"#4f46e5", width:`${it.pct}%`, borderRadius:999}}/>
                    </div>
                    <div style={{fontSize:12, color:"#666", textAlign:"right"}}>{it.pct}%</div>
                  </div>
                  <div style={{width:120, textAlign:"right"}}>
                    {it.status==="ready" && (
                      <button onClick={()=>uploadOne(i)} style={{padding:"6px 10px", borderRadius:6, border:"1px solid #ddd"}}>Upload</button>
                    )}
                    {it.status==="done" && <span style={{color:"#059669"}}>Done</span>}
                    {["presigning","uploading","confirming"].includes(it.status) && <span> {it.status}…</span>}
                    {it.status==="error" && <span style={{color:"#b91c1c"}}>Error</span>}
                  </div>
                </div>
                {it.err && <div style={{color:"#b91c1c", fontSize:12, marginTop:6}}>{it.err}</div>}
              </li>
            ))}
          </ul>
        </>
      )}
    </div>
  );
}


