"use client";
import {useEffect, useRef, useState} from "react";
import dynamic from "next/dynamic";
const Charts = dynamic(() => import("./charts"), {ssr:false, loading:() => <p className="empty-chart">Loading charts...</p>});
type Point = {x:number;y:number};
type Metrics = {processing_fps:number;elapsed_seconds:number;inference_average_ms:number;inference_median_ms:number;inference_p95_ms:number;model_only_fps:number;peak_ram_bytes:number;initialization_seconds:number};
type Results = {total:number;counts:Record<string,number>;directions:Record<string,number>;volume:{seconds:number;count:number}[];provider:string;model:string;metrics:Metrics};
type Job = {id:string;filename:string;status:string;provider?:string|null;width:number;height:number;fps:number;total_frames:number;processed_frames:number;progress:number;error?:string;line?:number[][];results?:Results};
type System = {model:string;model_ready:boolean;available_providers:string[];profile:string};
async function api<T>(path:string, init?:RequestInit):Promise<T> {
  const response = await fetch(`/api/${path}`,init);
  if(!response.ok){const body=await response.json().catch(()=>({detail:response.statusText}));throw new Error(typeof body.detail==="string"?body.detail:JSON.stringify(body.detail));}
  return response.json();
}
const classes=[{key:"car",label:"Cars",symbol:"\u25b0",color:"#4ee1b2"},{key:"motorcycle",label:"Motorcycles",symbol:"\u2301",color:"#87a7ff"},{key:"bus",label:"Buses",symbol:"\u25a4",color:"#f3bc70"},{key:"truck",label:"Trucks",symbol:"\u25a3",color:"#d89cf6"}];
export default function Dashboard(){
  const [system,setSystem]=useState<System|null>(null);
  const [job,setJob]=useState<Job|null>(null);
  const [points,setPoints]=useState<Point[]>([]);
  const [error,setError]=useState("");
  const [busy,setBusy]=useState(false);
  const [trails,setTrails]=useState(true);
  const [original,setOriginal]=useState<string|null>(null);
  const [showOriginal,setShowOriginal]=useState(false);
  const input=useRef<HTMLInputElement>(null);
  useEffect(()=>{
    api<System>("system").then(setSystem).catch(e=>setError(e.message));
    let saved:string|null=null;
    try{saved=localStorage.getItem("roadpulse.v1.job");}catch{/* Storage can be disabled by browser preferences. */}
    if(saved&&/^[0-9a-f]{32}$/.test(saved)){
      api<Job>(`jobs/${saved}`).then(restored=>{setJob(restored);if(restored.line)setPoints(restored.line.map(([x,y])=>({x,y})));}).catch(()=>{try{localStorage.removeItem("roadpulse.v1.job");}catch{}});
    }
  },[]);
  const id=job?.id;
  const active=job?.status==="QUEUED"||job?.status==="RUNNING";
  useEffect(()=>{
    if(!id||!active)return;
    const controller=new AbortController();
    let timer:ReturnType<typeof setTimeout>;
    async function poll(){
      try{const next=await api<Job>(`jobs/${id}`,{signal:controller.signal});setJob(next);if(next.status==="QUEUED"||next.status==="RUNNING")timer=setTimeout(poll,1000);}
      catch(e){if(!controller.signal.aborted){setError((e as Error).message);timer=setTimeout(poll,2000);}}
    }
    timer=setTimeout(poll,700);
    return()=>{controller.abort();clearTimeout(timer);};
  },[id,active]);
  useEffect(()=>()=>{if(original)URL.revokeObjectURL(original);},[original]);
  async function upload(file:File){
    setBusy(true);setError("");
    try{const form=new FormData();form.append("file",file);const next=await api<Job>("jobs",{method:"POST",body:form});setJob(next);try{localStorage.setItem("roadpulse.v1.job",next.id);}catch{}setPoints([]);setOriginal(URL.createObjectURL(file));setShowOriginal(false);}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function start(){
    if(!job||points.length!==2)return;
    setBusy(true);setError("");
    try{setJob(await api<Job>(`jobs/${job.id}/start`,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({line:points,trails})}));}
    catch(e){setError((e as Error).message);}finally{setBusy(false);}
  }
  async function cancel(){
    if(!job)return;
    try{setJob(await api<Job>(`jobs/${job.id}/cancel`,{method:"POST"}));}catch(e){setError((e as Error).message);}
  }
  const result=job?.results;
  const completed=job?.status==="COMPLETED";
  const canDraw=job?.status==="CREATED";
  const metric=(value:number|undefined,suffix="")=>value===undefined?"\u2014":`${value.toFixed(2)}${suffix}`;
  return <div className="shell">
    <aside className="rail"><a href="#" className="brand-icon" aria-label="RoadPulse home">R<span>Ã¢â‚¬Â¢</span></a><div className="rail-link selected" title="Analytics">Ã¢â€“Â¥</div><a className="rail-link" href="#workspace" aria-label="Video workspace">Ã¢â€“Â·</a><a className="rail-link" href="#exports" aria-label="Exports">Ã¢â€ â€œ</a><div className="rail-bottom">V1</div></aside>
    <div className="main-shell"><header className="topbar"><div><strong>ROADPULSE<span className="accent"> AI</span></strong><span className="header-separator">/</span><span className="muted">Traffic intelligence</span></div><div className="status-pill"><i className={system?"dot":"dot offline"}/>{system?"Local system online":"Connecting to local API"}</div></header>
    <main><div className="page-heading"><div><div className="eyebrow">OBSERVE. UNDERSTAND. MOVE FORWARD.</div><h1>Every movement.<br className="mobile-break"/> A clearer picture<span className="accent">.</span></h1><p className="muted">Turn traffic footage into actionable intelligence. Privately, on your machine.</p></div><div className="profile-card"><span className="chip">BALANCED</span><strong>YOLOX-Tiny</strong><small>{(result?.provider??job?.provider)?.replace("ExecutionProvider","")??"Provider selected at analysis"}</small></div></div>
    <div className="overview-grid"><section className="total-card"><div className="eyebrow">TOTAL CROSSINGS</div><div className="total-value">{result?.total??"\u2014"}<span>Ã¢â€ â€”</span></div><small>{result?"Computed from tracked line-crossing events":"Awaiting your first analysis"}</small></section>{classes.map(item=><section className="stat-card" key={item.key}><div className="stat-top"><span>{item.label}</span><span style={{color:item.color}}>{item.symbol}</span></div><strong>{result?.counts[item.key]??"\u2014"}</strong><div className="mini-rule" style={{background:item.color}}/><small>counted crossings</small></section>)}</div>
    <div className="workspace-grid"><section className="panel workspace" id="workspace"><div className="panel-title"><div><span className="section-number">01</span><h2>Video workspace</h2></div><span className="tag">{job?.status??"NO VIDEO"}</span></div>
      <div className="video-stage">
      {completed&&!showOriginal?<video key={job.id} src={`/api/jobs/${job.id}/artifacts/annotated.mp4`} controls playsInline aria-label="Annotated analysis video"/>:job?<div className="preview-canvas" style={{aspectRatio:`${job.width}/${job.height}`}}>
        {/* Backend-generated local image preserves exact source aspect ratio for normalized coordinates. */}
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img src={`/api/jobs/${job.id}/preview`} alt="First video frame. Set counting line using two points."/>
        <svg viewBox="0 0 1 1" preserveAspectRatio="none" aria-label="Counting line overlay">{points.length===2?<line x1={points[0].x} y1={points[0].y} x2={points[1].x} y2={points[1].y} stroke="#4ee1b2" strokeWidth=".004"/>:null}{points.map((p,i)=><circle key={i} cx={p.x} cy={p.y} r=".009" fill="#4ee1b2"/>)}</svg>
        {canDraw?<button className="draw-surface" aria-label="Place counting line endpoint" onClick={e=>{const rect=e.currentTarget.getBoundingClientRect();const p={x:Math.max(0,Math.min(1,(e.clientX-rect.left)/rect.width)),y:Math.max(0,Math.min(1,(e.clientY-rect.top)/rect.height))};setPoints(old=>old.length===2?[p]:[...old,p]);}}/>:null}
      </div>:<div className="upload-empty"><div className="upload-symbol">Ã¢â€ Â¥</div><h3>Your road. Your insights.</h3><p>Upload an MP4 traffic video to begin.</p><button className="primary" disabled={busy} onClick={()=>input.current?.click()}>{busy?"Uploading...":"Choose video"}<span>Ã¢â€ â€”</span></button><small>MP4 Ã‚Â· up to 1 GiB Ã‚Â· processed locally</small></div>}
      </div>
      {job&&original&&canDraw?<details className="original-preview"><summary>Play original video</summary><video src={original} controls playsInline aria-label="Original uploaded video"/></details>:null}
      <input ref={input} type="file" accept="video/mp4,.mp4" hidden onChange={e=>{const file=e.target.files?.[0];if(file)void upload(file);e.target.value="";}}/>
      <div className="workspace-controls"><div><strong>{job?.filename??"No video selected"}</strong><small>{canDraw?`${points.length}/2 line points Ã‚Â· Click the frame to place endpoints`:job?`${job.width} Ãƒâ€” ${job.height} Ã‚Â· ${job.fps.toFixed(2)} FPS`:"All analytics appear after real analysis"}</small></div><div className="button-row">{canDraw?<button className="secondary" onClick={()=>setPoints([])}>Reset line</button>:null}{!active?<button className="secondary" disabled={busy} onClick={()=>input.current?.click()}>Change video</button>:null}{completed?<button className="secondary" onClick={()=>setShowOriginal(v=>!v)}>{showOriginal?"Show analysis":"Show line"}</button>:null}</div></div>
      {canDraw?<div className="line-settings"><span>Or enter normalized endpoints</span>{points.length===2?points.map((point,index)=><div key={index} className="coordinate-row"><span>P{index+1}</span>{(["x","y"] as const).map(axis=><label key={axis}>{axis}<input type="number" min="0" max="1" step="0.01" value={point[axis]} onChange={e=>{const n=Number(e.target.value);if(Number.isFinite(n)&&n>=0&&n<=1)setPoints(old=>old.map((p,i)=>i===index?{...p,[axis]:n}:p));}}/></label>)}</div>):<button className="secondary" onClick={()=>setPoints([{x:.1,y:.5},{x:.9,y:.5}])}>Set horizontal line</button>}</div>:null}
      <div className="action-bar"><label><input type="checkbox" checked={trails} disabled={!canDraw} onChange={e=>setTrails(e.target.checked)}/> Movement trails</label>{active?<button className="secondary" onClick={()=>void cancel()}>Cancel analysis</button>:<button className="primary" disabled={!canDraw||points.length!==2||busy||!system?.model_ready} onClick={()=>void start()}>Start analysis <span>Ã¢â€ â€”</span></button>}</div>
      {job?<div className="progress-area" role="status"><div><span>{active?"Processing every frame":job.status}</span><span>{job.processed_frames} / {job.total_frames} frames Ã‚Â· {(job.progress*100).toFixed(0)}%</span></div><progress max="1" value={job.progress}/></div>:null}
      {error||job?.error?<p className="error" role="alert">{error||job?.error}</p>:null}
      {system&&!system.model_ready?<p className="notice">Model not prepared. Run <code>python scripts/prepare_model.py</code> in the project environment, then reload.</p>:null}
    </section>
    <div className="side-panels"><section className="panel"><div className="panel-title"><div><span className="section-number">02</span><h2>Directional flow</h2></div><span className="muted">Ã¢â€¡â€ž</span></div><div className="direction"><span className="direction-icon">Ã¢â€ â€”</span><div><strong>A Ã¢â€ â€™ B</strong><small>Negative to positive line side</small></div><b>{result?.directions.A_TO_B??"\u2014"}</b></div><div className="direction"><span className="direction-icon reverse">Ã¢â€ â„¢</span><div><strong>B Ã¢â€ â€™ A</strong><small>Positive to negative line side</small></div><b>{result?.directions.B_TO_A??"\u2014"}</b></div><p className="footnote">Directions follow the order of your line endpoints. Track IDs are temporary within this video.</p></section>
    <section className="panel"><div className="panel-title"><div><span className="section-number">03</span><h2>Analysis details</h2></div></div><dl className="details"><div><dt>Execution provider</dt><dd>{(result?.provider??job?.provider)?.replace("ExecutionProvider","")??"Awaiting analysis"}</dd></div><div><dt>Input resolution</dt><dd>{job?`${job.width} Ãƒâ€” ${job.height}`:"\u2014"}</dd></div><div><dt>Input frame rate</dt><dd>{metric(job?.fps," FPS")}</dd></div><div><dt>Pipeline throughput</dt><dd className="accent">{metric(result?.metrics.processing_fps," FPS")}</dd></div><div><dt>Model-only throughput</dt><dd>{metric(result?.metrics.model_only_fps," FPS")}</dd></div><div><dt>Inference avg / p95</dt><dd>{result?`${result.metrics.inference_average_ms.toFixed(1)} / ${result.metrics.inference_p95_ms.toFixed(1)} ms`:"\u2014"}</dd></div><div><dt>Total elapsed</dt><dd>{metric(result?.metrics.elapsed_seconds," s")}</dd></div><div><dt>Peak worker RAM</dt><dd>{result?`${(result.metrics.peak_ram_bytes/1024**2).toFixed(0)} MB`:"\u2014"}</dd></div></dl></section></div></div>
    <Charts result={result}/>
    <section className="panel exports" id="exports"><div><div className="eyebrow">TAKE YOUR INSIGHTS WITH YOU</div><h2>Ready for the next step.</h2><p className="muted">Download the annotated footage and the events behind every count.</p></div><div className="export-links">{[["annotated.mp4","Annotated MP4"],["events.csv","Events CSV"],["summary.json","Summary JSON"]].map(([file,label])=>completed?<a key={file} className="secondary" href={`/api/jobs/${job.id}/artifacts/${file}`} download>{label} Ã¢â€ â€œ</a>:<button key={file} className="secondary" disabled>{label} Ã¢â€ â€œ</button>)}</div></section>
    <footer><span>ROADPULSE AI <span className="muted">/ Local-first traffic intelligence</span></span><span className="muted">YOLOX + ByteTrack Ã‚Â· No cloud inference</span></footer></main></div></div>;
}
