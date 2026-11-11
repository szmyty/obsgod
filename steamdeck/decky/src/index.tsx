import { ButtonItem, PanelSection, PanelSectionRow, staticClasses } from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { health } from "./health.mjs";

type Diagnostic = {time:string; level:string; message:string};
type Result = {ok:boolean; state:string; message:string; configured?:boolean; stream?:{active:boolean; reconnecting:boolean; bytes:number; duration_ms:number}; recording_path?:string; diagnostics?:Diagnostic[]; plugin_version?:string};
const readStatus=callable<[],Result>("status");
const start=callable<[],Result>("start");
const stop=callable<[],Result>("stop");
const test=callable<[],Result>("test_recording");
const clearLogs=callable<[],Result>("clear_logs");
let result:Result|undefined;
let progressAt=0;
let previousBytes=0;
let lastPoll=0;
let polling=false;
let busy="";
let notice="";
let diagnostics:Diagnostic[]=[];
let pluginVersion="";
const listeners=new Set<()=>void>();
const changed=()=>listeners.forEach(listener=>listener());

async function refresh(){
  if(polling)return;polling=true;
  try{
    const next=await readStatus();
    const now=Date.now();
    if(next.stream?.active && next.stream.bytes>0 && (next.stream.bytes!==previousBytes || !result?.stream?.active)) progressAt=now;
    previousBytes=next.stream?.bytes??0; result=next;lastPoll=now;
    if(next.diagnostics)diagnostics=next.diagnostics;
    if(next.plugin_version)pluginVersion=next.plugin_version;
  }catch{
    result={ok:false,state:"unknown",message:"OBS connection unavailable. Use Stop streaming or inspect OBS."};
  }finally{polling=false;changed();}
}

function useStateView(){
  const [,render]=useState(0);
  useEffect(()=>{const listener=()=>render(value=>value+1);listeners.add(listener);return()=>{listeners.delete(listener);};},[]);
  const now=Date.now();
  const current=now-lastPoll>8000&&result?{...result,ok:false,state:"unknown"}:result;
  return health(current,progressAt,now);
}

function Dot(){const state=useStateView();return <span role="img" aria-label={state.label} style={{color:state.color,fontSize:24,lineHeight:1}}>●</span>;}

async function clearConsole(){
  try{
    const next=await clearLogs();
    if(next.diagnostics)diagnostics=next.diagnostics;
    if(!next.ok)notice=next.message;
  }catch{notice="Could not clear the console. Refresh status and try again.";}
  changed();
}

function Console(){
  // useStateView subscribes this component to the same updates as the dot.
  useStateView();
  const [page,setPage]=useState(0);
  const offset=Math.min(page,Math.max(0,Math.ceil(diagnostics.length/8)-1));
  const end=diagnostics.length-offset*8;
  const text=diagnostics.slice(Math.max(0,end-8),end).reverse().map(entry=>`${new Date(entry.time).toLocaleTimeString()} [${entry.level.toUpperCase()}] ${entry.message}`).join("\n\n");
  return <>
    <PanelSectionRow><div style={{fontWeight:700,marginTop:8}}>Diagnostic console{pluginVersion&&<small style={{display:"block",fontWeight:400,opacity:.7}}>Plugin {pluginVersion}</small>}</div></PanelSectionRow>
    <PanelSectionRow><div role="log" aria-label="OBSGod diagnostic console" aria-live="off" style={{background:"#111923",border:"1px solid #536274",borderRadius:4,padding:10,fontSize:12,lineHeight:1.5,whiteSpace:"pre-wrap",overflowWrap:"anywhere",userSelect:"text"}}>{text||"No diagnostic events yet. Open a game, then make a local test clip. The streaming dot stays red during a local recording."}</div></PanelSectionRow>
    <PanelSectionRow><div style={{fontSize:12,opacity:.75}}>Newest first · {diagnostics.length} / 100 events saved on this Deck across reloads and updates. Keys, URLs and raw OBS output are excluded.</div></PanelSectionRow>
    {diagnostics.length>8&&<>
      <PanelSectionRow><ButtonItem layout="below" disabled={end<=8} onClick={()=>setPage(offset+1)}>Older events</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={offset===0} onClick={()=>setPage(0)}>Latest events</ButtonItem></PanelSectionRow>
    </>}
    <PanelSectionRow><ButtonItem layout="below" onClick={()=>void clearConsole()}>Clear console</ButtonItem></PanelSectionRow>
  </>;
}

async function act(action:"start"|"stop"|"test"){
  if(busy&&action!=="stop")return;
  busy=action;notice=action==="test"?"Capturing a local test clip… nothing is being broadcast.":action==="start"?"Preparing capture and connecting…":"Stopping / cancelling…";changed();
  try{
    const next=await (action==="start"?start():action==="stop"?stop():test());
    notice=next.message+(next.recording_path?"\n"+next.recording_path:"");
    toaster.toast({title:next.ok?"OBSGod":"OBSGod needs attention",body:next.message});
  }catch{notice="Operation could not be confirmed. Press Stop streaming and check OBS.";}
  finally{busy="";await refresh();changed();}
}

function Content(){
  const state=useStateView();
  const seconds=Math.floor((result?.stream?.duration_ms??0)/1000);
  const duration=Math.floor(seconds/60)+":"+String(seconds%60).padStart(2,"0");
  return <>
    <PanelSection title="STREAM CONTROL">
      <PanelSectionRow><div role="status" aria-live="polite" style={{display:"flex",gap:12,alignItems:"center",padding:"8px 0",fontSize:20,fontWeight:700}}><span style={{color:state.color}}>●</span>{state.label}</div></PanelSectionRow>
      {result?.stream?.active&&<PanelSectionRow><div style={{fontSize:14,opacity:.8}}>Live output · {duration}</div></PanelSectionRow>}
      <PanelSectionRow><ButtonItem layout="below" disabled={!!busy||!result?.configured||!!result?.stream?.active} onClick={()=>act("start")}>Start streaming</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" onClick={()=>act("stop")}>Stop streaming / cancel</ButtonItem></PanelSectionRow>
      <PanelSectionRow><div style={{fontSize:13,lineHeight:1.5,opacity:.8}}>Green means OBS is sending output. Check your Kick channel on another device for picture and sound.</div></PanelSectionRow>
      <PanelSectionRow><div aria-live="polite" style={{fontSize:14,lineHeight:1.5,whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{notice||result?.message||"Checking the local OBS connection…"}</div></PanelSectionRow>
    </PanelSection>
    <PanelSection title="FIRST STREAM CHECK">
      <PanelSectionRow><ButtonItem layout="below" disabled={!!busy||!!result?.stream?.active||!result?.configured} onClick={()=>act("test")}>Make 10-second test clip</ButtonItem></PanelSectionRow>
      <PanelSectionRow><div style={{fontSize:13,lineHeight:1.5,opacity:.8}}>Open a game before starting. Test clips save to Videos/OBSGod. Enter your URL and key in OBSGod Setup in Desktop Mode. Microphone is off unless enabled there.</div></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" onClick={()=>refresh()}>Refresh status</ButtonItem></PanelSectionRow>
      <Console/>
    </PanelSection>
  </>;
}

export default definePlugin(()=>{
  void refresh();const timer=setInterval(()=>void refresh(),2500);
  return {name:"OBSGod",titleView:<div className={staticClasses.Title}>OBSGod <small style={{fontWeight:400,opacity:.7}}>preview</small></div>,content:<Content/>,icon:<Dot/>,onDismount(){clearInterval(timer);listeners.clear();}};
});
