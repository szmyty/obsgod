import {ButtonItem, DropdownItem, Focusable, GamepadButton, PanelSection, PanelSectionRow, SliderField} from "@decky/ui";
import {callable} from "@decky/api";
import {useEffect, useState} from "react";
import {mixerView, mixerGain} from "./mixer-state.mjs";
import {createTalkLease} from "./mixer-talk.mjs";
import {type ToolRunner} from "./Advanced";

export const mixerCall=callable<[payload:Record<string,unknown>],any>("mixer_action");
export function cancelPanelTalk(){void mixerCall({action:"talk-cancel"}).catch(()=>{});}
const hint={fontSize:13,lineHeight:1.5,opacity:.85,overflowWrap:"anywhere" as const};
function RowButton({children,disabled,onClick}:{children:string;disabled?:boolean;onClick:()=>void}){return <PanelSectionRow><ButtonItem layout="below" disabled={disabled} onClick={onClick}>{children}</ButtonItem></PanelSectionRow>;}

export function MixerTools({mixer,busy,run}:{mixer:any;busy:boolean;run:ToolRunner}){
  const state=mixerView(mixer,busy);
  const prefs=state.preferences;
  const [message,setMessage]=useState("");
  const [pending,setPending]=useState(false);
  const [holding,setHolding]=useState(false);
  const [gameGain,setGameGain]=useState(mixerGain(prefs.game_gain_percent));
  const [micGain,setMicGain]=useState(mixerGain(prefs.microphone_gain_percent));
  const [dirty,setDirty]=useState(false);
  const [lease]=useState(()=>createTalkLease((payload:Record<string,unknown>)=>mixerCall(payload),(active:boolean)=>setHolding(active),(error:string)=>setMessage(error)));
  useEffect(()=>{if(!dirty){setGameGain(mixerGain(prefs.game_gain_percent));setMicGain(mixerGain(prefs.microphone_gain_percent));}},[prefs.game_gain_percent,prefs.microphone_gain_percent,dirty]);
  useEffect(()=>{
    const stop=()=>lease.cancel();
    const hidden=()=>{if(document.hidden)stop();};
    window.addEventListener("blur",stop);window.addEventListener("pagehide",stop);document.addEventListener("visibilitychange",hidden);
    return()=>{window.removeEventListener("blur",stop);window.removeEventListener("pagehide",stop);document.removeEventListener("visibilitychange",hidden);lease.dispose();};
  },[lease]);
  useEffect(()=>{if(busy||state.talkDisabled)lease.release();},[busy,state.talkDisabled,lease]);
  async function configure(preferences:Record<string,unknown>){
    if(busy||pending)return;
    lease.release();setPending(true);setMessage("Applying microphone settings; waiting for OBS confirmation…");
    try{const reply=await run({kind:"mixer",payload:{action:"configure",preferences}});setMessage(reply.message??"Settings saved. Check the observed microphone state.");if(reply.ok&&("game_gain_percent" in preferences||"microphone_gain_percent" in preferences))setDirty(false);}
    catch(error){setMessage(error instanceof Error?error.message:"Audio action could not be confirmed. Saved preferences do not prove OBS is muted.");}
    finally{setPending(false);}
  }
  const disabled=busy||pending;
  const options=[{data:"default",label:"Follow system default (stays muted after a change)"},...(mixer?.devices??[]).filter((device:any)=>device.id!=="default").map((device:any)=>({data:device.id,label:`${device.label}${device.default?" · current default":""}${device.available===false?" · unavailable":""}`}))];
  if(prefs.microphone_device&&prefs.microphone_device!=="default"&&!options.some((option:any)=>option.data===prefs.microphone_device))options.push({data:prefs.microphone_device,label:"Saved input · currently unavailable"});
  const micName=(mixer?.devices??[]).find((device:any)=>device.id===prefs.microphone_device)?.label;
  const press=()=>{if(!state.talkDisabled&&!pending)lease.press();};
  return <PanelSection title="LIVE AUDIO & MICROPHONE">
    <PanelSectionRow><div role="status" aria-live="polite" style={{background:"#111923",border:"1px solid #536274",borderRadius:8,padding:12}}><strong>{pending?"Audio change pending…":state.label}</strong><div style={{...hint,marginTop:6}}>{state.fresh?"Observed from managed OBS":"OBS microphone state is unconfirmed; saved preferences shown below."}</div></div></PanelSectionRow>
    <PanelSectionRow><div style={hint}>These controls affect this stream and recording only. They do not mute your SteamOS microphone or game chat.</div></PanelSectionRow>
    <RowButton disabled={disabled||!state.enabled} onClick={()=>void configure({microphone_muted:true})}>Mute microphone on stream</RowButton>
    <RowButton disabled={disabled||state.unmuteDisabled} onClick={()=>void configure({microphone_muted:false})}>Unmute microphone on stream</RowButton>
    <PanelSectionRow><div style={hint}>Saved preference: {prefs.microphone_muted===true?"muted":prefs.microphone_muted===false?"unmuted":"not loaded"}{prefs.push_to_talk?" · hold-to-talk enabled":""}. Reconnecting does not clear a saved mute.</div></PanelSectionRow>
    <PanelSectionRow><div role="meter" aria-label="Microphone input level" aria-valuemin={-90} aria-valuemax={0} aria-valuenow={state.level} aria-valuetext={state.levelText} style={{height:12,background:"#253244",borderRadius:4}}><div style={{height:"100%",width:state.level===undefined?"0%":`${(state.level+90)/90*100}%`,background:"#80c6ef",borderRadius:4}}/></div><div style={hint}>{state.levelText}{state.microphone.signal==="silent"?" · no signal observed":""}</div></PanelSectionRow>
    <RowButton disabled={disabled} onClick={()=>void configure({microphone_enabled:!state.enabled,microphone_muted:true})}>{state.enabled?"Disable microphone capture":"Enable microphone capture · starts muted"}</RowButton>
    <PanelSectionRow><DropdownItem label="Microphone input" description={micName?`Saved input: ${micName}`:"Device changes start muted. Choose a device, then explicitly unmute."} rgOptions={options} selectedOption={prefs.microphone_device??"default"} disabled={disabled} onChange={option=>void configure({microphone_device:option.data,microphone_muted:true})}/></PanelSectionRow>
    <PanelSectionRow><SliderField label="Game / system audio gain" min={0} max={200} step={5} value={gameGain} valueSuffix="%" showValue disabled={disabled} onChange={value=>{setGameGain(value);setDirty(true);}}/></PanelSectionRow>
    <PanelSectionRow><SliderField label="Microphone gain" min={0} max={200} step={5} value={micGain} valueSuffix="%" showValue disabled={disabled} onChange={value=>{setMicGain(value);setDirty(true);}}/></PanelSectionRow>
    <RowButton disabled={disabled||!dirty} onClick={()=>void configure({game_gain_percent:gameGain,microphone_gain_percent:micGain})}>Apply audio levels</RowButton>
    <PanelSectionRow><div style={hint}>Game gain changes captured system audio, which may include other apps. 100% is unchanged; 0% is silent.</div></PanelSectionRow>
    <RowButton disabled={disabled} onClick={()=>void configure({push_to_talk:!prefs.push_to_talk,microphone_muted:true})}>{prefs.push_to_talk?"Disable hold-to-talk · keep muted":"Enable hold-to-talk · starts muted"}</RowButton>
    {prefs.push_to_talk&&<>
      <RowButton disabled={disabled||!state.fresh||!state.enabled||!state.available||state.systemMuted||prefs.microphone_muted===false} onClick={()=>void configure({microphone_muted:false})}>Arm hold-to-talk</RowButton>
      <PanelSectionRow><Focusable role="button" tabIndex={state.talkDisabled||pending?-1:0} aria-disabled={state.talkDisabled||pending} aria-pressed={holding} onOKActionDescription="Hold to talk" onButtonDown={event=>{if(event.detail.button===GamepadButton.OK)press();}} onButtonUp={event=>{if(event.detail.button===GamepadButton.OK)lease.release();}} onGamepadBlur={()=>lease.cancel()} onPointerDown={event=>{if(event.button===0){event.preventDefault();event.currentTarget.setPointerCapture?.(event.pointerId);press();}}} onPointerUp={()=>lease.release()} onPointerCancel={()=>lease.cancel()} onKeyDown={event=>{if((event.key===" "||event.key==="Enter")&&!event.repeat){event.preventDefault();press();}}} onKeyUp={event=>{if(event.key===" "||event.key==="Enter"){event.preventDefault();lease.release();}}} onBlur={()=>lease.cancel()} style={{padding:14,border:"2px solid #8da6bf",borderRadius:6,textAlign:"center",background:holding?"#254c60":"#1b2b3c",opacity:state.talkDisabled?.5:1}}>{holding?"Talking lease active · release to mute":"Hold here to talk"}</Focusable></PanelSectionRow>
      <PanelSectionRow><div style={hint}>Hold A, Enter, Space or this button while the panel has focus. This is not a global Steam shortcut. Releasing, leaving the panel or lease expiry requests mute. If OBS control is lost, mute cannot be verified; stop output or check OBS directly.</div></PanelSectionRow>
    </>}
    {mixer?.hardware?.guidance&&<PanelSectionRow><div style={hint}>{mixer.hardware.guidance}</div></PanelSectionRow>}
    {mixer?.notice?.message&&<PanelSectionRow><div role="status" style={hint}>{mixer.notice.message}</div></PanelSectionRow>}
    {message&&<PanelSectionRow><div aria-live="polite" style={hint}>{message}</div></PanelSectionRow>}
  </PanelSection>;
}
