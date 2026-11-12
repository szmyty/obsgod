import { ButtonItem, PanelSection, PanelSectionRow, staticClasses } from "@decky/ui";
import { callable, definePlugin, toaster } from "@decky/api";
import { useEffect, useState } from "react";
import { health } from "./health.mjs";
import { createView, currentResult, observe, controls } from "./state.mjs";

type Diagnostic = {time:string; level:string; message:string};
type Outcome = {id?:number; action?:string; ok:boolean; message:string; recording_path?:string};
type Result = {ok:boolean; state:string; message:string; configured?:boolean; output_known?:boolean; process?:string; connection?:string; recording?:boolean; capture?:string; frames?:string; game?:string; backend_id?:string; snapshot_id?:number; operation?:{id:number; action:string; state:string}|null; action_result?:Outcome; last_action?:Outcome; stream?:{active:boolean; reconnecting:boolean; bytes:number; duration_ms:number}; recording_path?:string; diagnostics?:Diagnostic[]; plugin_version?:string; settings?:{capture_mode?:"screen"|"game";idle_style?:"black"|"placeholder"};audio?:{state:string;message?:string}};
type UpdateResult = {ok:boolean; state:string; message:string; current_version?:string; latest_version?:string; available?:boolean; current_app_version?:string; current_plugin_version?:string; current_updater_version?:string; mismatch?:boolean; channel?:string};
const readStatus=callable<[],Result>("status");
const start=callable<[],Result>("start");
const stop=callable<[],Result>("stop");
const test=callable<[],Result>("test_recording");
const setCaptureMode=callable<[mode:string],Result>("set_capture_mode");
const clearLogs=callable<[],Result>("clear_logs");
const checkUpdates=callable<[],UpdateResult>("check_for_updates");
let result:Result|undefined;
const view=createView();
let pollTask:Promise<void>|undefined;
let requestSerial=0;
let actionSerial=0;
let currentAction=0;
let instance=0;
let active=false;
let busy="";
let notice="";
let actionNoticeAt=0;
let diagnostics:Diagnostic[]=[];
let pluginVersion="";
let updateChecking=false;
let updateInfo:UpdateResult|undefined;
const seenOutcomes=new Set<string>();
const listeners=new Set<()=>void>();
const changed=()=>listeners.forEach(listener=>listener());

function bounded<T>(promise:Promise<T>,milliseconds:number):Promise<T>{
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(new Error("Operation timed out")),milliseconds);
    promise.then(value=>{clearTimeout(timer);resolve(value);},error=>{clearTimeout(timer);reject(error);});
  });
}

function refresh():Promise<void>{
  if(pollTask)return pollTask;
  const generation=instance,epoch=view.epoch,request=++requestSerial;
  const task=(async()=>{
    let next:Result;
    try{next=await bounded(readStatus(),7500);}
    catch{next={ok:false,state:"unknown",output_known:false,message:"OBS connection unavailable. Use Stop streaming / recover or inspect OBS."};}
    if(!active||instance!==generation)return;
    const update=observe(view,next,Date.now(),request,epoch);
    if(!update.accepted)return;
    result=next;
    if(next.diagnostics)diagnostics=next.diagnostics;
    if(next.plugin_version)pluginVersion=next.plugin_version;
    // Only a confirmed output transition produces a streaming success toast.
    // An action reply, repeated click or temporary disconnect cannot do so.
    if(update.transition)toaster.toast({title:"OBSGod",body:update.transition==="streaming"?"OBS is streaming. Verify picture and sound on your channel.":"OBS confirms streaming has stopped."});
    changed();
  })();
  pollTask=task;
  void task.finally(()=>{if(pollTask===task)pollTask=undefined;});
  return task;
}

function useStateView(){
  const [,render]=useState(0);
  useEffect(()=>{const listener=()=>render(value=>value+1);listeners.add(listener);return()=>{listeners.delete(listener);};},[]);
  const now=Date.now();
  return health(currentResult(view,now),view.progressAt,now);
}

function Dot(){const state=useStateView();return <span role="img" aria-label={state.label} style={{color:state.color,fontSize:24,lineHeight:1}}>●</span>;}

async function clearConsole(){
  try{
    const next=await clearLogs();
    if(next.diagnostics)diagnostics=next.diagnostics;
    if(!next.ok){notice=next.message;actionNoticeAt=Date.now();}
  }catch{notice="Could not clear the console. Refresh status and try again.";actionNoticeAt=Date.now();}
  changed();
}

async function copyText(text:string){
  try{
    if(navigator.clipboard?.writeText){await navigator.clipboard.writeText(text);return;}
  }catch{/* Steam's browser may deny the asynchronous clipboard API. */}
  const focused=document.activeElement;
  const field=document.createElement("textarea");
  field.value=text;field.readOnly=true;field.setAttribute("aria-hidden","true");
  field.style.cssText="position:fixed;left:0;top:0;width:1px;height:1px;opacity:0";
  document.body.appendChild(field);
  try{
    field.select();
    if(!document.execCommand("copy"))throw new Error("Clipboard unavailable");
  }finally{
    field.remove();
    if(focused instanceof HTMLElement)focused.focus({preventScroll:true});
  }
}

function Console(){
  // useStateView subscribes this component to the same updates as the dot.
  useStateView();
  const [page,setPage]=useState(0);
  const [copying,setCopying]=useState(false);
  const [copyNotice,setCopyNotice]=useState("");
  const offset=Math.min(page,Math.max(0,Math.ceil(diagnostics.length/8)-1));
  const end=diagnostics.length-offset*8;
  const text=diagnostics.slice(Math.max(0,end-8),end).reverse().map(entry=>`${new Date(entry.time).toLocaleTimeString()} [${entry.level.toUpperCase()}] ${entry.message}`).join("\n\n");
  async function copyConsole(){
    if(copying||!diagnostics.length)return;
    // Copy only the already-filtered event history, never the status/settings
    // object or free-form operation results. Include every retained page.
    const entries=[...diagnostics].reverse();
    const payload=`OBSGod plugin ${pluginVersion||"unknown"}\n${entries.length} diagnostic events (newest first)\n\n`+entries.map(entry=>`${entry.time} [${entry.level.toUpperCase()}] ${entry.message}`).join("\n\n");
    setCopying(true);setCopyNotice("");
    try{
      await copyText(payload);
      setCopyNotice(`Copied ${entries.length} diagnostic ${entries.length===1?"event":"events"}. Paste them into your message.`);
    }catch{
      setCopyNotice("Could not access the clipboard. Select the console text or take a photo.");
    }finally{setCopying(false);}
  }
  return <>
    <PanelSectionRow><div style={{fontWeight:700,marginTop:8}}>Diagnostic console{pluginVersion&&<small style={{display:"block",fontWeight:400,opacity:.7}}>Plugin {pluginVersion}</small>}</div></PanelSectionRow>
    <PanelSectionRow><div role="log" aria-label="OBSGod diagnostic console" aria-live="off" style={{background:"#111923",border:"1px solid #536274",borderRadius:4,padding:10,fontSize:12,lineHeight:1.5,whiteSpace:"pre-wrap",overflowWrap:"anywhere",userSelect:"text"}}>{text||"No diagnostic events yet. Make a local test clip to check capture. The streaming dot stays red during a local recording."}</div></PanelSectionRow>
    <PanelSectionRow><div style={{fontSize:12,opacity:.75}}>Newest first · {diagnostics.length} / 100 events saved on this Deck across reloads and updates. Keys, URLs and raw OBS output are excluded.</div></PanelSectionRow>
    {/* Keep the focused button enabled while copying; the handler rejects a
        duplicate click. Disabling it would discard Steam/browser focus. */}
    <PanelSectionRow><ButtonItem layout="below" disabled={!diagnostics.length} onClick={()=>void copyConsole()}>{copying?"Copying…":"Copy console log"}</ButtonItem></PanelSectionRow>
    {copyNotice&&<PanelSectionRow><div aria-live="polite" style={{fontSize:13,lineHeight:1.5}}>{copyNotice}</div></PanelSectionRow>}
    {diagnostics.length>8&&<>
      <PanelSectionRow><ButtonItem layout="below" disabled={end<=8} onClick={()=>setPage(offset+1)}>Older events</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={offset===0} onClick={()=>setPage(0)}>Latest events</ButtonItem></PanelSectionRow>
    </>}
    <PanelSectionRow><ButtonItem layout="below" onClick={()=>void clearConsole()}>Clear console</ButtonItem></PanelSectionRow>
  </>;
}

async function act(action:"start"|"stop"|"test"){
  const available=controls(currentResult(view,Date.now()),busy);
  if(action==="start"?available.startDisabled:action==="test"?available.testDisabled:available.stopDisabled)return;
  const token=++actionSerial,generation=instance;
  currentAction=token;
  busy=action;view.epoch++;actionNoticeAt=0;
  notice=action==="test"?"Capturing a local test clip… nothing is being broadcast.":action==="start"?"Preparing capture and connecting…":"Stopping / cancelling…";changed();
  try{
    const next=await bounded(action==="start"?start():action==="stop"?stop():test(),95000);
    if(!active||instance!==generation||currentAction!==token)return;
    const outcome=next.action_result??next;
    actionNoticeAt=Date.now();
    notice=outcome.message+(outcome.recording_path?"\n"+outcome.recording_path:"");
    const key=`${next.backend_id??"local"}:${next.action_result?.id??token}`;
    if(!seenOutcomes.has(key)){
      seenOutcomes.add(key);
      if(!outcome.ok)toaster.toast({title:"OBSGod needs attention",body:outcome.message});
      else if(action==="test"&&outcome.recording_path)toaster.toast({title:"OBSGod",body:"Local test clip saved. Nothing was broadcast."});
    }
  }catch{
    if(active&&instance===generation&&currentAction===token){notice="Operation could not be confirmed. Use Stop streaming / recover and check OBS.";actionNoticeAt=Date.now();}
  }finally{
    if(active&&instance===generation&&currentAction===token){busy="";await refresh();changed();}
  }
}

function canChangeCaptureMode(current:Result|undefined){
  return !!current?.configured && current.output_known===true && !current.stream?.active &&
    !current.recording && !current.operation && !busy;
}

async function changeCaptureMode(){
  const current=currentResult(view,Date.now()) as Result|undefined;
  if(!canChangeCaptureMode(current))return;
  const mode=current?.settings?.capture_mode==="game"?"screen":"game";
  const token=++actionSerial,generation=instance;
  currentAction=token;busy="capture-mode";view.epoch++;actionNoticeAt=0;
  notice="Saving capture mode…";changed();
  try{
    const next=await bounded(setCaptureMode(mode),15000);
    if(!active||instance!==generation||currentAction!==token)return;
    const outcome=next.action_result??next;
    notice=outcome.message;actionNoticeAt=Date.now();
    if(!outcome.ok)toaster.toast({title:"OBSGod needs attention",body:outcome.message});
  }catch{
    if(active&&instance===generation&&currentAction===token){notice="Capture mode could not be confirmed. Refresh status before starting.";actionNoticeAt=Date.now();}
  }finally{
    if(active&&instance===generation&&currentAction===token){busy="";await refresh();changed();}
  }
}

async function checkForUpdates(){
  if(updateChecking)return;
  const generation=instance;
  updateChecking=true;changed();
  try{
    const next=await bounded(checkUpdates(),25000);
    if(active&&generation===instance)updateInfo=next;
  }catch{
    if(active&&generation===instance)updateInfo={ok:false,state:"error",message:"Could not check updates. Retry or use the bundled Desktop updater."};
  }finally{if(active&&generation===instance){updateChecking=false;changed();}}
}

function Content(){
  const state=useStateView();
  const current=currentResult(view,Date.now()) as Result|undefined;
  const available=controls(current,busy);
  const captureMode=current?.settings?.capture_mode==="game"?"game":"screen";
  const seconds=Math.floor((result?.stream?.duration_ms??0)/1000);
  const duration=Math.floor(seconds/60)+":"+String(seconds%60).padStart(2,"0");
  return <>
    <PanelSection title="STREAM CONTROL">
      <PanelSectionRow><div role="status" aria-live="polite" style={{display:"flex",gap:12,alignItems:"center",padding:"8px 0",fontSize:20,fontWeight:700}}><span style={{color:state.color}}>●</span>{state.label}</div></PanelSectionRow>
      {result?.stream?.active&&<PanelSectionRow><div style={{fontSize:14,opacity:.8}}>Last reported output · {duration}</div></PanelSectionRow>}
      <PanelSectionRow><ButtonItem layout="below" disabled={available.startDisabled} onClick={()=>act("start")}>Start streaming</ButtonItem></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={available.stopDisabled} onClick={()=>act("stop")}>{available.stopLabel}</ButtonItem></PanelSectionRow>
      <PanelSectionRow><div style={{fontSize:13,lineHeight:1.5,opacity:.8}}>Green means OBS is sending output. Check your Kick channel on another device for picture and sound.</div></PanelSectionRow>
      <PanelSectionRow><div aria-live="polite" style={{fontSize:14,lineHeight:1.5,whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{busy&&notice?notice:result?.message||"Checking the local OBS connection…"}</div></PanelSectionRow>
      {!busy&&notice&&actionNoticeAt>0&&<PanelSectionRow><div style={{fontSize:12,lineHeight:1.5,opacity:.8,whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>Last action · {new Date(actionNoticeAt).toLocaleTimeString()}: {notice}</div></PanelSectionRow>}
    </PanelSection>
    <PanelSection title="CAPTURE">
      <PanelSectionRow><div style={{fontSize:15,fontWeight:700}}>Capture mode: {captureMode==="game"?"Game only":"Entire screen"}</div></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" disabled={!canChangeCaptureMode(current)} onClick={()=>void changeCaptureMode()}>{busy==="capture-mode"?"Saving capture mode…":captureMode==="game"?"Switch to entire screen":"Switch to game only"}</ButtonItem></PanelSectionRow>
      <PanelSectionRow><div style={{fontSize:13,lineHeight:1.5,opacity:.8}}>Change modes while streaming and recording are stopped. Entire screen includes Steam menus. Game only uses the between-game screen when a compatible game source is unavailable; it never falls back to sharing the entire screen. Customize that screen in Desktop Setup.</div></PanelSectionRow>
      {current?.audio&&<PanelSectionRow><div style={{fontSize:13,lineHeight:1.5}}>Game audio: {current.audio.message||current.audio.state}. Check a local clip and your channel for sound.</div></PanelSectionRow>}
    </PanelSection>
    <PanelSection title="FIRST STREAM CHECK">
      <PanelSectionRow><ButtonItem layout="below" disabled={available.testDisabled} onClick={()=>act("test")}>Make 10-second test clip</ButtonItem></PanelSectionRow>
      <PanelSectionRow><div style={{fontSize:13,lineHeight:1.5,opacity:.8}}>Game only shows your between-game screen until compatible game capture is available. Entire screen must provide usable frames before a test or broadcast starts. Test clips save to Videos/OBSGod. Enter your URL and key in OBSGod Setup in Desktop Mode. Microphone is off unless enabled there.</div></PanelSectionRow>
      <PanelSectionRow><ButtonItem layout="below" onClick={()=>refresh()}>Refresh status</ButtonItem></PanelSectionRow>
      <Console/>
    </PanelSection>
    <PanelSection title="UPDATES">
      <PanelSectionRow><ButtonItem layout="below" disabled={updateChecking} onClick={()=>void checkForUpdates()}>{updateChecking?"Checking for updates…":"Check for updates"}</ButtonItem></PanelSectionRow>
      <PanelSectionRow><div aria-live="polite" style={{fontSize:13,lineHeight:1.5,whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{updateInfo?`${updateInfo.message}\nApp: ${updateInfo.current_app_version??updateInfo.current_version??"unknown"} · Plugin: ${updateInfo.current_plugin_version??pluginVersion??"unknown"} · Updater: ${updateInfo.current_updater_version??"unknown"}${updateInfo.latest_version?`\nLatest: ${updateInfo.latest_version}`:""}`:`Installed plugin: ${pluginVersion||"checking…"}`}</div></PanelSectionRow>
      <PanelSectionRow><div style={{fontSize:13,lineHeight:1.5,opacity:.8}}>Checking does not install anything or interrupt a stream. Apply updates in Desktop Mode with the bundled Update OBSGod launcher after streaming and recording are confirmed stopped.</div></PanelSectionRow>
    </PanelSection>
  </>;
}

export default definePlugin(()=>{
  active=true;instance++;view.epoch++;pollTask=undefined;
  void refresh();const timer=setInterval(()=>{void refresh();changed();},1500);
  return {name:"OBSGod",titleView:<div className={staticClasses.Title}>OBSGod <small style={{fontWeight:400,opacity:.7}}>preview</small></div>,content:<Content/>,icon:<Dot/>,onDismount(){active=false;instance++;view.epoch++;clearInterval(timer);listeners.clear();busy="";updateChecking=false;}};
});
