import { ButtonItem, PanelSection, PanelSectionRow, staticClasses } from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { health } from "./health.mjs";

type Result = {ok:boolean; state:string; message:string; configured?:boolean; stream?:{active:boolean; reconnecting:boolean; bytes:number; duration_ms:number}; recording_path?:string};
const readStatus=callable<[],Result>("status");
const start=callable<[],Result>("start");
const stop=callable<[],Result>("stop");
const test=callable<[],Result>("test_recording");
let result:Result|undefined;
let progressAt=0;
let previousBytes=0;
let lastPoll=0;
let polling=false;
let busy="";
let notice="";
const listeners=new Set<()=>void>();
const changed=()=>listeners.forEach(listener=>listener());

async function refresh(){
  if(polling)return;polling=true;
  try{
    const next=await readStatus();
    const now=Date.now();
    if(next.stream?.active && (next.stream.bytes>previousBytes || !result?.stream?.active)) progressAt=now;
    previousBytes=next.stream?.bytes??0; result=next;lastPoll=now;
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
    </PanelSection>
  </>;
}

export default definePlugin(()=>{
  void refresh();const timer=setInterval(()=>void refresh(),2500);
  return {name:"OBSGod",titleView:<div className={staticClasses.Title}>OBSGod <small style={{fontWeight:400,opacity:.7}}>preview</small></div>,content:<Content/>,icon:<Dot/>,onDismount(){clearInterval(timer);listeners.clear();}};
});
