import {ButtonItem,ConfirmModal,PanelSection,PanelSectionRow,showModal} from "@decky/ui";
import {callable} from "@decky/api";
import {useEffect,useRef,useState,type ReactNode} from "react";
import {createDependencyView,dependencyConsent,dependencyObservationFailed,dependencyView,observeDependencies,readSetupLater,rememberSetupLater} from "./setup-state.mjs";

export type SetupState="setup_required"|"ready"|"running"|"cancelling"|"cancelled"|"interrupted"|"failed";
export type SetupStatus={
  schema_version:1;ready:boolean;state:SetupState;message:string;
  reason:{code:string;message:string}|null;
  dependencies:{id:string;name:string;scope:string|null;ref:string|null;version:string|null;installed:boolean;compatible:boolean}[];
  remote:{configured:boolean;needs_add:boolean;valid:boolean;name:string;reason:string};
  operation:{id:string;state:string;stage:string;started_at:string;finished_at:string|null;
    progress:{time:string;level:string;message:string}[];cancel_requested:boolean}|null;
  can_install:boolean;can_cancel:boolean;
};
export type SetupReadiness={ready:boolean;reason:string;state:string};
const readStatus=callable<[],SetupStatus>("dependency_status");
const install=callable<[consent:boolean],SetupStatus>("install_dependencies");
const cancel=callable<[],SetupStatus>("cancel_dependency_setup");
const view=createDependencyView();
const listeners=new Set<()=>void>();
let request=0;
let pollTask:Promise<void>|undefined;
let localAction="";
let localMessage="";
let later=false;
let laterLoaded=false;
let confirmationOpen=false;
const changed=()=>listeners.forEach(listener=>listener());

function storage():Storage|undefined{try{return window.localStorage;}catch{return undefined;}}
function bounded<T>(promise:Promise<T>,milliseconds:number):Promise<T>{
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(new Error("Setup status timed out")),milliseconds);
    promise.then(value=>{clearTimeout(timer);resolve(value);},error=>{clearTimeout(timer);reject(error);});
  });
}

// Polls only observe the backend-owned job. Unmounting this panel never cancels
// a transaction; a reopened panel (including a frontend reload) reads its ID.
async function refreshDependencies():Promise<void>{
  if(localAction)return;
  if(pollTask)return pollTask;
  const token=++request,epoch=view.epoch;
  const task=(async()=>{
    try{
      const next=await bounded(readStatus(),12000);
      if(observeDependencies(view,next,Date.now(),token,epoch))localMessage="";
      else{
        if(epoch===view.epoch&&token>=view.latestRequest)throw new Error("Unrecognized setup status");
      }
    }catch{
      if(dependencyObservationFailed(view,token,epoch))localMessage="Could not check dependency setup. The backend job may still be running. Recheck status; do not reinstall OBS manually while a transaction is active.";
    }finally{changed();}
  })();
  pollTask=task;
  try{await task;}finally{if(pollTask===task)pollTask=undefined;}
}

async function setupAction(action:"install"|"cancel"){
  const state=dependencyView(view,Date.now(),localAction);
  if(action==="install"?!state.canInstall:!state.canCancel)return;
  localAction=action;localMessage="";
  const token=++request,epoch=++view.epoch;
  if(action==="install"){later=false;rememberSetupLater(storage(),false);}
  changed();
  try{
    // Starting a job returns promptly; installation itself has the backend's
    // multi-minute budget, independent of OBS startup/request timeouts.
    const next=await bounded(action==="install"?install(true):cancel(),15000);
    if(!observeDependencies(view,next,Date.now(),token,epoch)&&epoch===view.epoch)throw new Error("Unrecognized setup status");
  }catch{
    dependencyObservationFailed(view,token,epoch);
    localMessage=action==="install"?"Setup request could not be confirmed. Check status to recover the existing job before trying again.":"Cancellation could not be confirmed. Check status; keep the Deck on until the transaction is stopped.";
  }finally{localAction="";changed();void refreshDependencies();}
}

function postponeSetup(){later=true;rememberSetupLater(storage(),true);changed();}
function showInstallConsent(){
  if(confirmationOpen||!dependencyView(view,Date.now(),localAction).canInstall)return;
  confirmationOpen=true;
  const items=dependencyConsent(view.status);
  const requirements=JSON.stringify(items);
  let modal:ReturnType<typeof showModal>;
  const close=()=>{confirmationOpen=false;modal?.Close();};
  try{
    modal=showModal(<ConfirmModal strTitle="Install streaming dependencies?"
      strDescription={<div style={{fontSize:15,lineHeight:1.5}}>
        <p>Setup uses OBS Studio and its compatible GStreamer extension. It downloads and installs the following for your SteamOS user account:</p>
        <ul>{items.map((item:string,index:number)=><li key={index}>{item}</li>)}</ul>
        <p>Flatpak may also download required runtimes. Existing compatible dependencies are reused. SteamOS stays read-only; ordinary OBS settings and shared apps are preserved.</p>
        <p>Setup runs in the background. It never starts OBS or broadcasts. You can cancel setup from this panel.</p>
      </div>}
      strOKButtonText="Install" strCancelButtonText="Later"
      onOK={()=>{
        close();
        if(JSON.stringify(dependencyConsent(view.status))!==requirements){localMessage="Dependency requirements changed. Review setup again before installing.";changed();return;}
        void setupAction("install");
      }}
      onCancel={()=>{postponeSetup();close();}} closeModal={close}/>,undefined,{fnOnClose:()=>{confirmationOpen=false;}});
  }catch{confirmationOpen=false;localMessage="Could not open the setup confirmation. Reopen the panel and try again.";changed();}
}

function Hint({children}:{children:ReactNode}){return <div style={{fontSize:13,lineHeight:1.5,overflowWrap:"anywhere",whiteSpace:"pre-wrap"}}>{children}</div>;}
function RowButton({children,disabled,onClick}:{children:ReactNode;disabled?:boolean;onClick:()=>void}){
  return <PanelSectionRow><ButtonItem layout="below" disabled={disabled} onClick={onClick}>{children}</ButtonItem></PanelSectionRow>;
}

export function DependencySetup({onReadiness}:{onReadiness?:(state:SetupReadiness)=>void}){
  const [,render]=useState(0);
  const [details,setDetails]=useState(false);
  const readinessListener=useRef(onReadiness);
  readinessListener.current=onReadiness;
  useEffect(()=>{
    if(!laterLoaded){later=readSetupLater(storage());laterLoaded=true;}
    const listener=()=>render(value=>value+1);
    listeners.add(listener);
    void refreshDependencies();
    const timer=setInterval(()=>{listener();void refreshDependencies();},5000);
    return()=>{listeners.delete(listener);clearInterval(timer);};
  },[]);
  const state=dependencyView(view,Date.now(),localAction);
  const status=view.status as SetupStatus|undefined;
  useEffect(()=>{readinessListener.current?.({ready:state.ready,reason:state.reason,state:state.state});},[state.ready,state.reason,state.state]);
  const operation=status?.operation;
  const progress=Array.isArray(operation?.progress)?operation.progress.slice(-6):[];
  const showDetails=details||!state.ready;
  return <PanelSection title="DEPENDENCY SETUP">
    <PanelSectionRow><div role="status" aria-live="polite"><strong>{state.title}</strong><Hint>{state.reason}</Hint></div></PanelSectionRow>
    {later&&!state.ready&&!state.busy&&<PanelSectionRow><Hint>Setup postponed. The plugin remains installed; streaming and local tests stay unavailable until its dependencies are ready. You can install them below whenever you are ready.</Hint></PanelSectionRow>}
    {state.ready&&<RowButton onClick={()=>setDetails(value=>!value)}>{details?"Hide dependency details":"Show dependency details"}</RowButton>}
    {showDetails&&<>
      <PanelSectionRow><Hint>{status?.dependencies?.map(dependency=>`${dependency.name}: ${dependency.installed?dependency.compatible?"Installed and compatible":"Installed; compatibility needs attention":"Missing"}${dependency.scope?` (${dependency.scope})`:""}${dependency.version?` · ${dependency.version}`:""}`).join("\n")||"Checking the actual OBS and GStreamer Flatpak installations…"}</Hint></PanelSectionRow>
      {status?.remote?.needs_add&&<PanelSectionRow><Hint>Setup also needs the official Flathub remote for your user account. Adding it requires your Install confirmation.</Hint></PanelSectionRow>}
      {operation&&<PanelSectionRow><Hint>Setup stage: {operation.stage||operation.state}{"\n"}Job: {operation.id}{state.busy?"\nYou can close this panel and return later. Setup keeps running.":""}</Hint></PanelSectionRow>}
      {progress.length>0&&<PanelSectionRow><div role="log" aria-label="Dependency setup progress" aria-live="off" style={{background:"#111923",border:"1px solid #536274",borderRadius:4,padding:10,fontSize:12,lineHeight:1.5,whiteSpace:"pre-wrap",overflowWrap:"anywhere"}}>{progress.map(entry=>`[${entry.level.toUpperCase()}] ${entry.message}`).join("\n")}</div></PanelSectionRow>}
    </>}
    {!state.ready&&!state.busy&&<>
      <RowButton disabled={!state.canInstall} onClick={showInstallConsent}>{["failed","cancelled","interrupted"].includes(state.state)?"Review and retry setup":"Install dependencies…"}</RowButton>
      <RowButton onClick={postponeSetup}>Later</RowButton>
    </>}
    {state.busy&&<RowButton disabled={!state.canCancel} onClick={()=>void setupAction("cancel")}>{localAction==="cancel"||state.state==="cancelling"?"Cancelling setup…":"Cancel dependency setup"}</RowButton>}
    {state.state==="running"&&status?.can_cancel!==true&&!localAction&&<PanelSectionRow><Hint>A previous setup worker is still finishing. This session cannot safely cancel it. Wait for it to finish, then check setup status; do not start another installation or delete its files.</Hint></PanelSectionRow>}
    <RowButton disabled={!!localAction} onClick={()=>{localMessage="";void refreshDependencies();}}>{pollTask?"Checking setup status…":"Check setup status"}</RowButton>
    {localMessage&&<PanelSectionRow><div role="status"><Hint>{localMessage}</Hint></div></PanelSectionRow>}
    {!state.ready&&<PanelSectionRow><Hint>Help: keep network and free storage available during installation. If Flatpak or permissions are unavailable, use Discover in Desktop Mode to install OBS Studio and its compatible GStreamer extension, then check setup status here. Do not install another WebSocket plugin. Existing shared dependencies are never removed by this setup.</Hint></PanelSectionRow>}
  </PanelSection>;
}
