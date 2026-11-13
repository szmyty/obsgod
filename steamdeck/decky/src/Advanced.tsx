import {ButtonItem, PanelSection, PanelSectionRow} from "@decky/ui";
import {callable} from "@decky/api";
import {useEffect, useState, type ReactNode} from "react";
import {healthFresh, mediaControls, metricText, profileSummary} from "./advanced-state.mjs";

type Profile={version:number;width:number;height:number;fps:number;bitrate:number;encoder:string;microphone:boolean;capture_mode:string};
type Preset={name:string;label:string;description:string;profile:Profile};
type Profiles={ok:boolean;message:string;current?:Profile;profile?:Profile;profiles?:{name:string;profile:Profile}[];presets?:Preset[];warnings?:string[];document?:unknown};
type Clip={name:string;kind:string;bytes:number;modified_utc:string};
type Reply={ok:boolean;message:string;clips?:Clip[];recording_path?:string;[key:string]:unknown};
type ToolKind="profiles"|"idle"|"media"|"health"|"cancel-media"|"recovery";
export type ToolCommand={kind:ToolKind;payload:Record<string,unknown>};
export type ToolRunner=(command:ToolCommand)=>Promise<any>;
const profileCall=callable<[payload:Record<string,unknown>],Profiles>("stream_profiles");
const idleCall=callable<[payload:Record<string,unknown>],Reply>("set_idle_media");
const mediaCall=callable<[payload:Record<string,unknown>],Reply>("media_action");
const healthCall=callable<[],any>("stream_health");
const cancelMediaCall=callable<[],any>("cancel_media_operation");
const recoveryCall=callable<[],any>("retry_recovery");
export function invokeTool(command:ToolCommand):Promise<any>{
  return command.kind==="profiles"?profileCall(command.payload):command.kind==="idle"?idleCall(command.payload):command.kind==="media"?mediaCall(command.payload):command.kind==="cancel-media"?cancelMediaCall():command.kind==="recovery"?recoveryCall():healthCall();
}
function Hint({children}:{children:ReactNode}){return <div style={{fontSize:13,lineHeight:1.5,opacity:.85,overflowWrap:"anywhere",whiteSpace:"pre-wrap"}}>{children}</div>;}
function RowButton({children,disabled,onClick}:{children:ReactNode;disabled?:boolean;onClick:()=>void}){return <PanelSectionRow><ButtonItem layout="below" disabled={disabled} onClick={onClick}>{children}</ButtonItem></PanelSectionRow>;}
function useAlive(){const [alive]=useState(()=>({current:true}));useEffect(()=>{alive.current=true;return()=>{alive.current=false;};},[alive]);return alive;}

export function StreamTools({current,busy,run,copy}:{current:any;busy:boolean;run:ToolRunner;copy:(text:string)=>Promise<void>}){
  const [profilesOpen,setProfilesOpen]=useState(false);
  const [profiles,setProfiles]=useState<Profiles>();
  const [presetIndex,setPresetIndex]=useState(0);
  const [savedIndex,setSavedIndex]=useState(0);
  const [preview,setPreview]=useState<Profiles>();
  const [resetConfirm,setResetConfirm]=useState(false);
  const [message,setMessage]=useState("");
  const alive=useAlive();
  const media=mediaControls(current,busy);
  const preset=profiles?.presets?.[presetIndex % Math.max(1,profiles?.presets?.length??0)];
  const saved=profiles?.profiles?.[savedIndex % Math.max(1,profiles?.profiles?.length??0)];
  async function request(command:ToolCommand){
    try{const reply=await run(command);if(alive.current){setMessage(reply.message??"Action completed; confirm status.");return reply;}}
    catch(error){if(alive.current)setMessage(error instanceof Error?error.message:"Action could not be confirmed. Refresh status before retrying.");}
  }
  async function loadProfiles(){
    setProfilesOpen(true);
    const reply=await request({kind:"profiles",payload:{action:"list"}});
    if(reply&&alive.current)setProfiles(reply);
  }
  async function previewPreset(){if(!preset)return;const reply=await request({kind:"profiles",payload:{action:"preview",preset:preset.name}});if(reply&&alive.current)setPreview(reply);}
  async function saveCurrent(){const reply=await request({kind:"profiles",payload:{action:"save",name:"deck-saved"}});if(reply?.ok)await loadProfiles();}
  async function applyProfile(payload:Record<string,unknown>){const reply=await request({kind:"profiles",payload});if(reply?.ok)await loadProfiles();}
  async function exportCurrent(){
    const reply=await request({kind:"profiles",payload:{action:"export"}});
    if(reply?.ok&&reply.document){try{await copy(JSON.stringify(reply.document,null,2));setMessage("Copied a settings-only profile. No server, stream key or local media path is included.");}catch{setMessage("Clipboard unavailable. Export the profile in Desktop Setup instead.");}}
  }
  return <>
    <PanelSection title="STREAM PROFILES">
      <PanelSectionRow><Hint>Saved settings apply only to your next explicit start. Presets are starting points, not measured Steam Deck performance guarantees.</Hint></PanelSectionRow>
      <RowButton disabled={busy} onClick={()=>profilesOpen?setProfilesOpen(false):void loadProfiles()}>{profilesOpen?"Hide stream profiles":"Open stream profiles"}</RowButton>
      {profilesOpen&&<>
        <PanelSectionRow><Hint>Current: {profileSummary(profiles?.current)}</Hint></PanelSectionRow>
        {preset&&<>
          <RowButton disabled={busy} onClick={()=>{setPresetIndex(value=>value+1);setPreview(undefined);}}>Preset: {preset.label} · choose next</RowButton>
          <PanelSectionRow><Hint>{profileSummary(preset.profile)}{"\n"}{preset.description}</Hint></PanelSectionRow>
          <RowButton disabled={busy} onClick={()=>void previewPreset()}>Preview selected preset</RowButton>
          <RowButton disabled={!media.idle} onClick={()=>void applyProfile({action:"apply",preset:preset.name})}>Apply selected preset</RowButton>
        </>}
        {preview&&<PanelSectionRow><Hint>{preview.message}{"\n"}{profileSummary(preview.profile)}{preview.warnings?.map(warning=>"\n"+warning).join("")}</Hint></PanelSectionRow>}
        {saved&&<>
          <RowButton disabled={busy} onClick={()=>setSavedIndex(value=>value+1)}>Saved: {saved.name} · choose next</RowButton>
          <PanelSectionRow><Hint>{profileSummary(saved.profile)}</Hint></PanelSectionRow>
          <RowButton disabled={!media.idle} onClick={()=>void applyProfile({action:"apply",name:saved.name})}>Apply saved profile</RowButton>
        </>}
        <RowButton disabled={busy||!profiles?.current} onClick={()=>void saveCurrent()}>Save current as deck-saved</RowButton>
        <RowButton disabled={busy} onClick={()=>void exportCurrent()}>Copy settings-only profile</RowButton>
        <RowButton disabled={!media.idle} onClick={()=>{if(!resetConfirm)setResetConfirm(true);else{setResetConfirm(false);void applyProfile({action:"reset"});}}}>{resetConfirm?"Confirm reset: entire screen, microphone off":"Reset stream settings to defaults"}</RowButton>
        <RowButton disabled={busy} onClick={()=>void loadProfiles()}>Reload profiles</RowButton>
        <PanelSectionRow><Hint>Use Desktop Setup for exact quality controls, profile names/import and game-profile bindings. A bound profile applies only during an explicit cold Start/Test/record/replay action; a game launch never starts output. Applying a profile preserves your destination and key. Stop all output before applying; a running managed OBS may need to be closed before new encoder settings take effect.</Hint></PanelSectionRow>
      </>}
      {message&&<PanelSectionRow><div role="status"><Hint>{message}</Hint></div></PanelSectionRow>}
    </PanelSection>
    <PanelSection title="BETWEEN GAMES">
      <PanelSectionRow><Hint>Selected: {current?.settings?.idle_style??"black"}. Game-only capture never switches to the full display automatically.</Hint></PanelSectionRow>
      <RowButton disabled={!media.idle} onClick={()=>void request({kind:"idle",payload:{idle_style:"black"}})}>Use black between-game screen</RowButton>
      <RowButton disabled={!media.idle} onClick={()=>void request({kind:"idle",payload:{idle_style:"placeholder",idle_text:current?.settings?.idle_text??"Game starting soon"}})}>Use saved between-game message</RowButton>
      {current?.settings?.idle_media&&<RowButton disabled={!media.idle} onClick={()=>void request({kind:"idle",payload:{idle_style:current.settings.idle_media.match(/\.(mp4|webm)$/i)?"video":"image"}})}>Use saved custom media</RowButton>}
      <PanelSectionRow><Hint>Import your own licensed image or video in Desktop Setup. It is copied locally for offline use. Between-game videos are always muted; your selected system audio and microphone policy stay in effect. No media selection starts a broadcast.</Hint></PanelSectionRow>
    </PanelSection>
  </>;
}

export function MediaTools({current,busy,mediaPending,run}:{current:any;busy:boolean;mediaPending:string;run:ToolRunner}){
  const [open,setOpen]=useState(false),[clips,setClips]=useState<Clip[]>([]),[message,setMessage]=useState("");
  const [latest,setLatest]=useState("");
  const [serial]=useState(()=>({value:0}));
  const alive=useAlive();
  const state=mediaControls(current,busy);
  async function action(name:string){
    const token=++serial.value;
    try{const reply=await run({kind:name==="cancel-media"?"cancel-media":"media",payload:{action:name}});if(!alive.current||token!==serial.value)return;setMessage(reply.message??"Confirm the current output state before another action.");if(reply.recording_path)setLatest(reply.recording_path);if(reply.clips)setClips(reply.clips);}
    catch(error){if(alive.current&&token===serial.value)setMessage(error instanceof Error?error.message:"Media action could not be confirmed. Use Stop/recover and inspect OBS.");}
  }
  const storage=current?.media?.storage;
  const free=typeof storage?.available_bytes==="number"?`${(storage.available_bytes/1024**3).toFixed(1)} GiB available`:"Free space not confirmed";
  return <PanelSection title="RECORDING & REPLAY">
    <PanelSectionRow><Hint>Recording: {state.known?(state.recording?"Active":"Stopped"):"Unconfirmed"}{"\n"}Replay buffer: {state.known?(state.replay?"Active":"Stopped"):"Unconfirmed"}{"\n"}{free}</Hint></PanelSectionRow>
    {["record-start","replay-start"].includes(mediaPending)&&<RowButton onClick={()=>void action("cancel-media")}>Cancel local media startup</RowButton>}
    <RowButton disabled={state.recordStartDisabled} onClick={()=>void action("record-start")}>Start local recording</RowButton>
    <RowButton disabled={state.recordStopDisabled} onClick={()=>void action("record-stop")}>{state.known?"Stop & save recording":"Stop recording / recover"}</RowButton>
    <RowButton disabled={state.replayStartDisabled} onClick={()=>void action("replay-start")}>Start replay buffer</RowButton>
    <RowButton disabled={state.replaySaveDisabled} onClick={()=>void action("replay-save")}>Save replay clip</RowButton>
    <RowButton disabled={state.replayStopDisabled} onClick={()=>void action("replay-stop")}>{state.known?"Stop replay buffer":"Stop replay / recover"}</RowButton>
    {message&&<PanelSectionRow><div role="status"><Hint>{message}{latest?"\nSaved: "+latest:""}</Hint></div></PanelSectionRow>}
    <PanelSectionRow><Hint>These actions never start a stream. Stopping streaming preserves independent recording/replay. Use the focused panel buttons with your controller; no global button chord is registered.</Hint></PanelSectionRow>
    <RowButton disabled={busy} onClick={()=>{setOpen(value=>!value);if(!open)void action("list");}}>{open?"Hide saved clips":"Browse saved clips"}</RowButton>
    {open&&<>
      <PanelSectionRow><Hint>{clips.length?clips.slice(0,12).map(clip=>`${clip.kind} · ${clip.name}\n${(clip.bytes/1024**2).toFixed(1)} MiB · ${new Date(clip.modified_utc).toLocaleString()}`).join("\n\n"):"No finalized managed clips listed. Existing or interrupted files are preserved; inspect the recording folder in Desktop Mode."}</Hint></PanelSectionRow>
      <PanelSectionRow><Hint>Folder: {storage?.directory??"Not confirmed"}. Change the recording folder, replay duration, reserve and explicit retention/export choices in Desktop Setup. No automatic clip deletion is enabled by default.</Hint></PanelSectionRow>
    </>}
  </PanelSection>;
}

export function HealthTools({current,busy,run}:{current:any;busy:boolean;run:ToolRunner}){
  const [open,setOpen]=useState(false),[report,setReport]=useState<any>(),[message,setMessage]=useState("");
  const alive=useAlive();
  const [clock,setClock]=useState(Date.now());
  useEffect(()=>{if(!open)return;const timer=setInterval(()=>setClock(Date.now()),1000);return()=>clearInterval(timer);},[open]);
  const embedded=current?.stream_health;
  const observed=!report?embedded:embedded&&Date.parse(embedded.observed_at)>Date.parse(report.observed_at)?embedded:report;
  useEffect(()=>{
    if(!open)return;
    let stopped=false,pending=false;
    const timer=setInterval(async()=>{
      if(pending)return;pending=true;
      try{
        const reply=await Promise.race([healthCall(),new Promise((_,reject)=>setTimeout(()=>reject(new Error("Health observation timed out")),6000))]);
        if(!stopped){setReport((reply as any).data??reply);setClock(Date.now());}
      }catch{if(!stopped){setReport({message:"Health observation unavailable"});setClock(Date.now());}}
      finally{pending=false;}
    },5000);
    return()=>{stopped=true;clearInterval(timer);};
  },[open]);
  const fresh=healthFresh(observed,clock);
  async function sample(){
    setOpen(true);
    try{const reply=await run({kind:"health",payload:{}});if(alive.current){setReport(reply);setClock(Date.now());setMessage(reply.message??"");}}
    catch(error){if(alive.current)setMessage(error instanceof Error?error.message:"Health observation unavailable.");}
  }
  return <PanelSection title="STREAM HEALTH">
    <RowButton disabled={busy} onClick={()=>void sample()}>Measure current stream health</RowButton>
    {open&&<>
      <PanelSectionRow><div role="status"><Hint>{fresh?observed?.message??message:"Measurements expired or unavailable. Measure again; last values are not current health."}</Hint></div></PanelSectionRow>
      <PanelSectionRow><Hint>Bitrate: {metricText(observed,"bitrate_kbps"," kbps",clock,0)}{"\n"}Network-dropped frames: {metricText(observed,"stream_dropped_percent","%",clock)}{"\n"}Encoder-skipped frames: {metricText(observed,"encode_skipped_percent","%",clock)}{"\n"}Render-missed frames: {metricText(observed,"render_missed_percent","%",clock)}{"\n"}CPU: {metricText(observed,"cpu_percent","%",clock)}{"\n"}OBS frame rate: {metricText(observed,"fps"," fps",clock)}{"\n"}GPU: {metricText(observed,"gpu_percent","%",clock)}{"\n"}Audio: {fresh?observed?.audio??"unknown":"unknown"}{"\n"}Capture: {fresh?observed?.capture??"unknown":"unknown"}</Hint></PanelSectionRow>
      {fresh&&observed?.advice?.map((advice:{code:string;message:string})=><PanelSectionRow key={advice.code}><Hint>{advice.message}</Hint></PanelSectionRow>)}
      <PanelSectionRow><Hint>Updates every five seconds while these details are open. Measured locally; nothing is uploaded. OBS sending output does not prove your provider or viewers receive picture and sound. Missing metrics stay unknown. Quality settings never change automatically.</Hint></PanelSectionRow>
      <RowButton onClick={()=>setOpen(false)}>Hide stream health</RowButton>
    </>}
    <RowButton disabled={busy||(!current?.stream?.active&&!current?.recording&&!current?.media?.replay_active)} onClick={()=>void run({kind:"recovery",payload:{}}).catch(()=>setMessage("Recovery could not be confirmed; inspect OBS."))}>Retry bounded audio/capture recovery</RowButton>
    {current?.resilience&&<PanelSectionRow><Hint>Recovery: {current.resilience.message??current.resilience.state??"Not confirmed"}. Recovery never restarts a stopped broadcast.</Hint></PanelSectionRow>}
  </PanelSection>;
}
