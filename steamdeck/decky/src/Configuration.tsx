import {ButtonItem,ConfirmModal,DropdownItem,Navigation,PanelSection,PanelSectionRow,showModal,SliderField,TextField,ToggleField} from "@decky/ui";
import {callable} from "@decky/api";
import {useEffect,useRef,useState,type ReactNode} from "react";
import {configurationControls,configurationDraft,configurationPayload,destinationChanged,inferredProvider,openProviderGuide,providers,publicConfiguration,validateControlPassword,validateDestination} from "./configuration-state.mjs";
import {boundedRequest as bounded,settingsTimeouts} from "./action-timeouts.mjs";

type Settings={version:number;server:string;bitrate:number;fps:number;encoder:string;width:number;height:number;capture_mode:string;microphone:boolean};
type Connection={ok:boolean;host:string;port:string;authentication_required:boolean;credentials_available:boolean;connected:boolean;managed:boolean;process:string;output_known:boolean;state:string;awaiting_verification?:boolean;message:string};
export type ConfigurationStatus={schema_version:1;ok:boolean;configured:boolean;key_configured:boolean;settings:Settings;connection:Connection;output_known:boolean;can_configure:boolean;can_close:boolean;message:string;action_result?:{id?:number;action?:string;ok:boolean;message:string}};
const readConfiguration=callable<[],ConfigurationStatus>("configuration_status");
const configureDestination=callable<[payload:Record<string,unknown>],ConfigurationStatus>("configure_destination");
const testConnection=callable<[],ConfigurationStatus>("test_control_connection");
const closeOBS=callable<[],ConfigurationStatus>("close_managed_obs");
const changePassword=callable<[payload:{password?:string;confirm:true;generate?:boolean}],ConfigurationStatus>("change_control_password");
const hintStyle={fontSize:13,lineHeight:1.5,overflowWrap:"anywhere" as const,whiteSpace:"pre-wrap" as const};
function Hint({children}:{children:ReactNode}){return <div style={hintStyle}>{children}</div>;}
function RowButton({children,disabled,onClick}:{children:ReactNode;disabled?:boolean;onClick:()=>void}){return <PanelSectionRow><ButtonItem layout="below" disabled={disabled} onClick={onClick}>{children}</ButtonItem></PanelSectionRow>;}
// Project only named public fields. Neither a future settings property nor an
// unexpected backend property can populate a key/password field in this form.
function publicView(value:ConfigurationStatus):ConfigurationStatus{
  const projected=publicConfiguration(value);
  if(!projected)throw new Error("Unrecognized configuration status");
  return projected as ConfigurationStatus;
}

export function Configuration({busy=false,onChanged,onOpenDesktopSetup}:{busy?:boolean;onChanged?:()=>void;onOpenDesktopSetup?:()=>void}){
  const [status,setStatus]=useState<ConfigurationStatus>();
  const [draft,setDraft]=useState<Settings>(()=>configurationDraft() as Settings);
  const [provider,setProvider]=useState("kick");
  const [key,setKey]=useState("");
  const [showKey,setShowKey]=useState(false);
  const [replaceKey,setReplaceKey]=useState(false);
  const [edited,setEdited]=useState<Record<string,boolean>>({});
  const [pending,setPending]=useState("");
  const [message,setMessage]=useState("");
  const [observedAt,setObservedAt]=useState(0);
  const [clock,setClock]=useState(Date.now());
  const [editing,setEditing]=useState(false);
  const [connectionOpen,setConnectionOpen]=useState(false);
  const [guidePending,setGuidePending]=useState(false),[guideNotice,setGuideNotice]=useState("");
  const guideAction=useRef(false);
  const [qualityOpen,setQualityOpen]=useState(false);
  const [controlOpen,setControlOpen]=useState(false);
  const [password,setPassword]=useState("");
  const [showPassword,setShowPassword]=useState(false);
  const alive=useRef(true),request=useRef(0),action=useRef(""),dirty=useRef(false),poll=useRef(false);
  const current=useRef<ConfigurationStatus|undefined>(undefined),lastObserved=useRef(0),baselineProvider=useRef("kick");
  const secret=useRef(""),controlSecret=useRef(""),sensitiveEpoch=useRef(0),modal=useRef<ReturnType<typeof showModal>|undefined>(undefined);
  const busyRef=useRef(busy);busyRef.current=busy;
  const onChangedRef=useRef(onChanged);onChangedRef.current=onChanged;

  function clearKey(){secret.current="";setKey("");setShowKey(false);sensitiveEpoch.current++;}
  function clearPassword(){controlSecret.current="";setPassword("");setShowPassword(false);}
  function toggleEditing(){
    if(action.current)return;
    if(editing){
      clearKey();clearPassword();modal.current?.Close();modal.current=undefined;
      const saved=current.current,selected=saved?.configured?inferredProvider(saved.settings.server):"kick";
      setDraft(configurationDraft(saved?.settings) as Settings);setEdited({});dirty.current=false;
      baselineProvider.current=selected;setProvider(selected);setReplaceKey(false);
      setQualityOpen(false);setControlOpen(false);setConnectionOpen(false);
    }
    setEditing(value=>!value);
  }
  function toggleConnection(){
    if(action.current)return;
    if(connectionOpen){clearPassword();modal.current?.Close();modal.current=undefined;setControlOpen(false);}
    setConnectionOpen(value=>!value);
  }
  async function openGuide(){
    if(guideAction.current)return;
    guideAction.current=true;setGuidePending(true);setGuideNotice("");
    try{await openProviderGuide(provider,(url:string)=>Navigation.NavigateToExternalWeb(url));}
    catch{if(alive.current)setGuideNotice("Could not open the provider setup guide. Try again when the browser is available, or open your provider's official help in Desktop Mode.");}
    finally{guideAction.current=false;if(alive.current)setGuidePending(false);}
  }
  function accept(raw:ConfigurationStatus,reset=false){
    const next=publicView(raw),previous=current.current;
    // First-run setup opens once. Ordinary polls never reopen a saved editor
    // or collapse a focused draft after Save.
    if(next.configured===false&&previous?.configured!==false)setEditing(true);
    const switched=!!previous&&previous.settings.server!==next.settings.server;
    current.current=next;lastObserved.current=Date.now();setStatus(next);setObservedAt(lastObserved.current);setClock(lastObserved.current);
    if(reset||!dirty.current||switched){
      setDraft(next.settings);setEdited({});dirty.current=false;
      const selected=next.configured?inferredProvider(next.settings.server):"kick";
      baselineProvider.current=selected;setProvider(selected);setReplaceKey(false);
    }
    if(switched){clearKey();clearPassword();if(!reset)setMessage("The saved destination changed. Private drafts were cleared; check the destination before saving.");}
  }
  async function refresh(reset=false){
    if(poll.current||action.current)return;
    poll.current=true;
    const token=++request.current;
    try{
      const next=await bounded(readConfiguration(),settingsTimeouts.configurationRead,"Configuration request timed out");
      if(alive.current&&token===request.current)accept(next,reset);
    }catch{
      if(alive.current&&token===request.current){lastObserved.current=0;setObservedAt(0);setMessage("Could not confirm configuration readiness. Refresh settings before saving or changing the local password.");}
    }finally{poll.current=false;}
  }
  useEffect(()=>{
    alive.current=true;void refresh();
    const timer=setInterval(()=>{setClock(Date.now());void refresh();},5000);
    return()=>{alive.current=false;request.current++;clearInterval(timer);secret.current="";controlSecret.current="";sensitiveEpoch.current++;modal.current?.Close();};
  },[]);

  const controls=configurationControls(status,observedAt,clock,{busy:busy||!!pending});
  const guide=providers[provider as keyof typeof providers]??providers.custom;
  const saved={...status,provider:baselineProvider.current};
  const changedDestination=destinationChanged(saved,provider,draft.server);
  const keyNeeded=!status?.configured||replaceKey||changedDestination;
  function edit(name:keyof Settings,value:string|number|boolean){
    if(name==="server")clearKey();
    dirty.current=true;setDraft(previous=>({...previous,[name]:value}));setEdited(previous=>({...previous,[name]:true}));
  }
  function changeProvider(value:string){
    if(!providers[value as keyof typeof providers]||value===provider)return;
    clearKey();clearPassword();dirty.current=true;setProvider(value);setReplaceKey(true);
  }
  async function pasteKey(){
    if(!controls.canConfigure||action.current)return;
    const epoch=++sensitiveEpoch.current;
    try{
      if(!navigator.clipboard?.readText)throw new Error("Clipboard unavailable");
      const value=await navigator.clipboard.readText();
      if(!alive.current||epoch!==sensitiveEpoch.current)return;
      if(!value||new TextEncoder().encode(value.trim()).length>4096||/[\r\n\0]/.test(value.trim())){setMessage("The clipboard does not contain a usable stream key. Paste it into the key field using the Steam keyboard instead.");return;}
      secret.current=value.trim();setKey(secret.current);setShowKey(false);dirty.current=true;setMessage("Pasted a new key draft. It stays hidden until you choose Show; save when the destination is correct.");
    }catch{if(alive.current&&epoch===sensitiveEpoch.current)setMessage("Clipboard access is unavailable. Select the stream-key field and use the Steam keyboard's paste control or a physical keyboard.");}
  }
  async function run(kind:"save"|"test"|"password"|"close",payload?:Record<string,unknown>){
    const allowed=configurationControls(current.current,lastObserved.current,Date.now(),{busy:busyRef.current||!!action.current});
    if(kind==="save"?!allowed.canConfigure:kind==="password"?!allowed.canChangePassword:kind==="close"?!allowed.canClose:!allowed.canTest){
      if(payload){if("stream_key" in payload)payload.stream_key="";if("password" in payload)payload.password="";}
      setMessage("The observed state changed. Refresh settings and confirm it is safe before retrying.");return;
    }
    action.current=kind;setPending(kind);setMessage(kind==="save"?"Saving private settings… nothing will be broadcast.":kind==="test"?"Testing the existing local OBS connection…":kind==="close"?"Closing the idle managed OBS instance…":"Updating the private local control password…");
    const token=++request.current;
    try{
      const next=await bounded(kind==="save"?configureDestination(payload??{}):kind==="test"?testConnection():kind==="close"?closeOBS():changePassword(payload as {password?:string;confirm:true;generate?:boolean}),settingsTimeouts.configurationAction,"Configuration request timed out");
      if(!alive.current||token!==request.current)return;
      accept(next,kind==="save"&&next.action_result?.ok===true);
      const outcome=next.action_result??next;
      setMessage(outcome.message||"Request completed. Confirm the observed state before starting.");
      onChangedRef.current?.();
    }catch{
      if(alive.current&&token===request.current){lastObserved.current=0;setObservedAt(0);setMessage("The request could not be confirmed. Refresh settings before retrying. No stream was started by this action.");}
    }finally{
      if(payload){if("stream_key" in payload)payload.stream_key="";if("password" in payload)payload.password="";}
      if(alive.current){if(kind==="save")clearKey();if(kind==="password")clearPassword();setPending("");}
      else{secret.current="";controlSecret.current="";}
      action.current="";
    }
  }
  function save(){
    if(action.current||!controls.canConfigure)return;
    const problem=validateDestination(saved,provider,draft,secret.current,replaceKey);
    if(problem){setMessage(problem);clearKey();return;}
    const payload=configurationPayload(saved,provider,draft,secret.current,edited,replaceKey);
    if(!Object.keys(payload).length){setMessage("No settings changed. Your saved destination and private key are unchanged.");clearKey();return;}
    clearKey();void run("save",payload);
  }
  function confirmPassword(generate:boolean){
    if(!controls.canChangePassword||action.current||modal.current)return;
    if(!generate){const problem=validateControlPassword(controlSecret.current);if(problem){setMessage(problem);clearPassword();return;}}
    const dismissed=()=>{modal.current=undefined;controlSecret.current="";if(alive.current){setPassword("");setShowPassword(false);}};
    const close=()=>{modal.current?.Close();dismissed();};
    modal.current=showModal(<ConfirmModal strTitle="Change the managed OBS password?"
      strDescription="This replaces only the local OBS control password. Your destination stream key stays separate. Managed OBS must be closed; no stream will start. The password is stored privately and will not be displayed or copied back."
      strOKButtonText={generate?"Generate private password":"Save private password"} strCancelButtonText="Cancel"
      onOK={()=>{const payload={confirm:true,password:generate?"":controlSecret.current,generate};close();void run("password",payload);}}
      onCancel={close} closeModal={close}/>,undefined,{fnOnClose:dismissed});
  }
  function confirmClose(){
    if(!controls.canClose||action.current||modal.current)return;
    const close=()=>{modal.current?.Close();modal.current=undefined;};
    modal.current=showModal(<ConfirmModal strTitle="Close managed OBS to edit settings?"
      strDescription="The managed OBS instance is currently observed idle. This closes only that instance so you can edit your destination or local password. It does not start OBS again or broadcast. If output begins or its state becomes unknown, the backend will refuse to close it."
      strOKButtonText="Close managed OBS" strCancelButtonText="Cancel"
      onOK={()=>{close();void run("close");}} onCancel={close} closeModal={close}/>,undefined,{fnOnClose:()=>{modal.current=undefined;}});
  }
  return <>
    <PanelSection title="STREAM DESTINATION">
      <PanelSectionRow><div role="status" aria-live="polite"><strong>{status?.configured?"Destination saved privately":"Configure your stream destination"}</strong><Hint>{controls.reason}</Hint></div></PanelSectionRow>
      <RowButton disabled={!!pending} onClick={toggleEditing}>{editing?"Hide destination settings":status?.configured?"Edit saved destination":"Configure stream destination"}</RowButton>
      {editing&&<>
      {controls.canClose&&<RowButton onClick={confirmClose}>Close managed OBS to edit settings…</RowButton>}
      <PanelSectionRow><DropdownItem label="Destination guide" description="Guidance only; changing this never contacts a provider or starts streaming." rgOptions={Object.entries(providers).map(([data,value])=>({data,label:value.name}))} selectedOption={provider} disabled={!controls.canConfigure} onChange={option=>changeProvider(option.data)}/></PanelSectionRow>
      <PanelSectionRow><Hint>{guide.help}</Hint></PanelSectionRow>
      <RowButton disabled={guidePending} onClick={()=>void openGuide()}>{guidePending?"Opening provider setup guide…":`Open ${guide.name} setup guide`}</RowButton>
      {"preset" in guide&&<RowButton disabled={!controls.canConfigure} onClick={()=>edit("server",guide.preset)}>Use Twitch secure server</RowButton>}
      <PanelSectionRow><TextField label="Stream server URL" aria-label="Stream server URL" description={guide.placeholder} value={draft.server} disabled={!controls.canConfigure} bShowCopyAction={false} onChange={event=>edit("server",event.target.value)}/></PanelSectionRow>
      <PanelSectionRow><TextField label="Stream key" aria-label="Stream key" description={keyNeeded?"Enter a new key for this destination/account. The key is never put in the server URL.":"Saved privately. Leave blank to keep it for this same destination only."} bIsPassword={!showKey} bShowCopyAction={false} bShowClearAction value={key} disabled={!controls.canConfigure} onChange={event=>{sensitiveEpoch.current++;secret.current=event.target.value;setKey(event.target.value);dirty.current=true;}}/></PanelSectionRow>
      <RowButton disabled={!controls.canConfigure||!key} onClick={()=>setShowKey(value=>!value)}>{showKey?"Hide stream key":"Show stream key"}</RowButton>
      <RowButton disabled={!controls.canConfigure} onClick={()=>void pasteKey()}>Paste stream key</RowButton>
      <PanelSectionRow><ToggleField label="Different account or event on the same server" description="Requires a new key even when the server URL is unchanged." checked={replaceKey} disabled={!controls.canConfigure} onChange={value=>{clearKey();clearPassword();setReplaceKey(value);dirty.current=true;}}/></PanelSectionRow>
      <PanelSectionRow><Hint>Select a field with your controller. STEAM + X opens the on-screen keyboard; normal typing and paste are supported. Keys start hidden and private drafts clear on Save, destination changes, hiding settings and panel close. A saved key is never read back.</Hint></PanelSectionRow>
      <RowButton onClick={()=>setQualityOpen(value=>!value)}>{qualityOpen?"Hide stream settings":"Stream quality & capture settings"}</RowButton>
      {qualityOpen&&<>
        <PanelSectionRow><SliderField label="Video bitrate" min={1000} max={8000} step={100} value={draft.bitrate} valueSuffix=" kbps" showValue disabled={!controls.canConfigure} onChange={value=>edit("bitrate",value)}/></PanelSectionRow>
        <PanelSectionRow><DropdownItem label="Frame rate" rgOptions={[{data:30,label:"30 fps · starting point"},{data:60,label:"60 fps · higher load"}]} selectedOption={draft.fps} disabled={!controls.canConfigure} onChange={option=>edit("fps",option.data)}/></PanelSectionRow>
        <PanelSectionRow><DropdownItem label="Output resolution" rgOptions={[{data:"960x540",label:"960 × 540 · lower load"},{data:"1280x720",label:"1280 × 720 · starting point"},{data:"1920x1080",label:"1920 × 1080 · qualify first"}]} selectedOption={`${draft.width}x${draft.height}`} disabled={!controls.canConfigure} onChange={option=>{const [width,height]=String(option.data).split("x").map(Number);edit("width",width);edit("height",height);}}/></PanelSectionRow>
        <PanelSectionRow><DropdownItem label="H.264 encoder" rgOptions={[{data:"vaapi",label:"AMD hardware · Steam Deck"},{data:"x264",label:"Software fallback · higher CPU load"}]} selectedOption={draft.encoder} disabled={!controls.canConfigure} onChange={option=>edit("encoder",option.data)}/></PanelSectionRow>
        <PanelSectionRow><DropdownItem label="Video capture" description="Game-only video never silently falls back to the entire screen. Captured system audio may include other applications." rgOptions={[{data:"screen",label:"Entire screen"},{data:"game",label:"Game only · idle between games"}]} selectedOption={draft.capture_mode} disabled={!controls.canConfigure} onChange={option=>edit("capture_mode",option.data)}/></PanelSectionRow>
        <PanelSectionRow><ToggleField label="Initial microphone capture" description="Initial setting only. Existing live mute/gain preferences stay intact; use Live audio & microphone for observed controls." checked={draft.microphone} disabled={!controls.canConfigure} onChange={value=>edit("microphone",value)}/></PanelSectionRow>
        <PanelSectionRow><Hint>Defaults are 720p, 30 fps, 4500 kbps and AMD hardware H.264. They are starting points, not a measured performance guarantee. Saved advanced options and idle media are preserved unless you edit them.</Hint></PanelSectionRow>
      </>}
      <RowButton disabled={!controls.canConfigure} onClick={save}>{pending==="save"?"Saving settings…":"Save destination & settings"}</RowButton>
      </>}
      <RowButton disabled={!!pending||busy} onClick={()=>void refresh()}>Refresh settings</RowButton>
      {guideNotice&&<PanelSectionRow><div role="status" aria-live="polite"><Hint>{guideNotice}</Hint></div></PanelSectionRow>}
      {onOpenDesktopSetup&&<RowButton disabled={!!pending||busy} onClick={onOpenDesktopSetup}>Show Desktop Setup instructions</RowButton>}
      <PanelSectionRow><Hint>Save never broadcasts. When ready, use a local test clip to check picture and sound, then explicitly Start streaming. If settings are locked, stop streaming, recording and replay, wait for confirmed idle state, then use Close managed OBS to edit settings.</Hint></PanelSectionRow>
    </PanelSection>
    <PanelSection title="LOCAL OBS CONNECTION">
      <RowButton disabled={!!pending} onClick={toggleConnection}>{connectionOpen?"Hide local connection controls":"Show local connection controls"}</RowButton>
      {connectionOpen&&<>
      <PanelSectionRow><Hint>{status?.connection?.host??"127.0.0.1"}:{status?.connection?.port??"4457"} · Password authentication required{"\n"}{status?.connection?.message??"Refresh settings to inspect the managed local connection."}</Hint></PanelSectionRow>
      <RowButton disabled={!controls.canTest} onClick={()=>void run("test")}>{pending==="test"?"Testing local connection…":"Test local OBS connection"}</RowButton>
      <PanelSectionRow><Hint>This read-only test authenticates an already running managed OBS. It does not launch OBS, record, contact your provider or start streaming. A working control connection does not prove viewers receive audio/video.</Hint></PanelSectionRow>
      <RowButton onClick={()=>{setControlOpen(value=>!value);clearPassword();}}>{controlOpen?"Hide local password controls":"Manage local OBS password"}</RowButton>
      {controlOpen&&<>
        <PanelSectionRow><Hint>The OBS control password is generated and stored privately during initial setup. It is different from your stream key and local setup authorization. Change or reset it only after managed OBS is fully closed.</Hint></PanelSectionRow>
        <PanelSectionRow><TextField label="New local OBS password" aria-label="New local OBS password" description="12–128 bytes; leave blank when generating a private password." bIsPassword={!showPassword} bShowCopyAction={false} bShowClearAction value={password} disabled={!controls.canChangePassword} onChange={event=>{controlSecret.current=event.target.value;setPassword(event.target.value);}}/></PanelSectionRow>
        <RowButton disabled={!controls.canChangePassword||!password} onClick={()=>setShowPassword(value=>!value)}>{showPassword?"Hide local password":"Show local password"}</RowButton>
        <RowButton disabled={!controls.canChangePassword||!password} onClick={()=>confirmPassword(false)}>Change local OBS password…</RowButton>
        <RowButton disabled={!controls.canChangePassword} onClick={()=>confirmPassword(true)}>Generate a new private OBS password…</RowButton>
      </>}
      </>}
    </PanelSection>
    {message&&<PanelSection title="CONFIGURATION RESULT"><PanelSectionRow><div role="status" aria-live="polite"><Hint>{message}</Hint></div></PanelSectionRow></PanelSection>}
  </>;
}
