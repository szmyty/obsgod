"use strict";
const fragment = window.location.hash.slice(1);
if (fragment) window.sessionStorage.setItem("obsgodSetupToken", fragment);
const token = fragment || window.sessionStorage.getItem("obsgodSetupToken") || "";
window.history.replaceState(null, "", "/");
const el = (id) => document.getElementById(id);
// Provider guides are hints, not account integration. URLs and keys still come
// from the owner's dashboard; switching guides never changes either field.
const providers = {
  kick:{name:"Kick",help:"Creator Dashboard → Channel → Stream URL and Key. Copy your own server and key, then set the stream title and category. The URL can be account-specific; prefer RTMPS when provided.",docs:"https://help.kick.com/en/articles/7066931-how-to-stream-on-kick-com",placeholder:"rtmps://your-kick-ingest-server:443/app"},
  twitch:{name:"Twitch",help:"Copy your primary stream key from Twitch Creator Dashboard → Settings → Stream. The recommended secure default server comes from Twitch's public ingest list. Choose another official ingest if needed; do not append the key to the server URL.",docs:"https://dev.twitch.tv/docs/video-broadcast/",placeholder:"rtmps://ingest.global-contribute.live-video.net/app",preset:"rtmps://ingest.global-contribute.live-video.net/app"},
  youtube:{name:"YouTube",help:"Enable live streaming on your account and create or select the intended stream in YouTube Live Control Room. Use its lock icon to copy the RTMPS Stream URL, then copy that event's stream key. Check whether you must also press Go Live in YouTube; OBS sending bytes does not prove the event is public.",docs:"https://support.google.com/youtube/answer/10364924?hl=en",placeholder:"Copy the RTMPS Stream URL from Live Control Room"},
  custom:{name:"Custom RTMP(S)",help:"Use the server URL and separate stream key supplied by your destination. RTMPS encrypts transport; plain RTMP is also supported for local/offline workflows. Server URLs must not contain credentials, query strings or the stream key.",docs:"https://obsproject.com/kb/quick-start-guide",placeholder:"rtmps://your-ingest-server/app"}
};
let savedServer = "", savedKey = false, controlCanChange = false, controlBusy = false;
let savedIdleMedia = "", savedIdleRights = "";
function inferredProvider(server) {
  try {
    const host = new URL(server).hostname.toLowerCase();
    if (host === "ingest.global-contribute.live-video.net" || host.endsWith(".contribute.live-video.net") || host.endsWith(".twitch.tv")) return "twitch";
    if (host === "a.rtmps.youtube.com" || host === "b.rtmps.youtube.com" || host === "a.rtmp.youtube.com" || host === "b.rtmp.youtube.com") return "youtube";
    if (host.endsWith(".global-contribute.live-video.net")) return "kick";
  } catch {}
  return "custom";
}
function updateProviderGuide() {
  const provider = providers[el("provider").value] || providers.custom;
  el("provider-help").textContent = provider.help;
  el("provider-docs").href = provider.docs;
  el("server").placeholder = provider.placeholder;
  el("provider-preset").disabled = !provider.preset;
}
function updateDestination() {
  const changed = savedKey && el("server").value.trim() !== savedServer;
  el("key").required = !savedKey || changed;
  el("key-help").textContent = changed ? "Server changed: enter the key for this destination. The previously saved key will not be sent to a different server automatically." : "Leave the key blank to keep it only when the server URL is unchanged. A new server requires its own key.";
  try {el("destination-status").textContent = "Destination host: " + new URL(el("server").value).hostname;} catch {el("destination-status").textContent = "Enter the server URL from your destination's dashboard.";}
}
async function api(path, body) {
  const response = await fetch(path, {method: body ? "POST" : "GET", headers: {"Authorization": "Bearer " + token, "Content-Type": "application/json"}, body: body ? JSON.stringify(body) : undefined, cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || "Setup connection failed");
  return data;
}
function message(id, data) { el(id).textContent = data.message; el(id).className = data.ok === false ? "error" : "success"; }
async function refresh() {
  const data = await api("/api/status");
  if(data.mixer)renderMixer(data.mixer);
  if (data.product_name) {el("product-name").textContent = "● " + data.product_name;document.title = data.product_name + " · Steam Deck setup";}
  if (data.settings) {
    for (const id of ["server", "bitrate", "fps", "encoder"]) el(id).value = data.settings[id];
    el("resolution").value = `${data.settings.width||1280}x${data.settings.height||720}`;
    savedIdleMedia=data.settings.idle_media||"";savedIdleRights=data.settings.idle_media_rights||"";
    el("capture_mode").value = data.settings.capture_mode || "screen";
    el("idle_style").value = data.settings.idle_style || "black";
    el("idle_text").value = data.settings.idle_text ?? "Game starting soon";
    updateIdleFields();
    el("microphone").checked = data.settings.microphone;
  }
  if (data.configured) el("key").placeholder = "Saved securely · leave blank to keep";
  savedServer = data.settings?.server || "";
  savedKey = !!data.configured;
  el("provider").value = inferredProvider(savedServer);
  updateProviderGuide();updateDestination();
  el("zip-path").textContent = data.plugin_zip;
  el("decky-status").textContent = data.decky_status?.message || "Decky service readiness has not been verified.";
  if (!data.flatpak) message("dependency-status", {ok:false,message:"Flatpak was not found. This installer is intended for SteamOS / Steam Deck."});
  await refreshConnection();
}
el("provider").addEventListener("change", updateProviderGuide);
el("server").addEventListener("input", updateDestination);
el("provider-preset").addEventListener("click", () => {
  const preset = providers[el("provider").value]?.preset;
  if (!preset) return;
  if (el("server").value && el("server").value !== preset && !window.confirm("Replace the server URL with the recommended server? Your key is not changed. A different saved server requires its own key.")) return;
  el("server").value = preset;updateDestination();
});
updateProviderGuide();updateDestination();
function updateIdleFields() {
  el("idle_style").disabled = el("capture_mode").value !== "game";
  el("idle_text").disabled = el("capture_mode").value !== "game" || el("idle_style").value !== "placeholder";
}
el("capture_mode").addEventListener("change", updateIdleFields);
el("idle_style").addEventListener("change", updateIdleFields);
updateIdleFields();
el("settings").addEventListener("submit", async (event) => {
  event.preventDefault(); el("save").disabled = true;
  const settings = {version:1, server:el("server").value.trim(), stream_key:el("key").value.trim(), width:Number(el("resolution").value.split("x")[0]), height:Number(el("resolution").value.split("x")[1]), idle_media:savedIdleMedia, idle_media_rights:savedIdleRights, bitrate:Number(el("bitrate").value), fps:Number(el("fps").value), encoder:el("encoder").value, microphone:el("microphone").checked, capture_mode:el("capture_mode").value, idle_style:el("idle_style").value, idle_text:el("idle_text").value};
  try {const data=await api("/api/action", {action:"configure",settings});message("save-status", data);if(data.ok){savedServer=settings.server;savedKey=true;el("key").value="";el("key").placeholder="Saved securely · leave blank to keep";updateDestination();await refreshConnection();}}
  catch(error){message("save-status", {ok:false,message:error.message});}
  finally{settings.stream_key="";el("save").disabled=false;}
});
el("dependencies").addEventListener("click", async () => {
  el("dependencies").disabled=true;
  try {
    message("dependency-status", await api("/api/action", {action:"dependencies"}));
    let data;do {await new Promise(resolve=>setTimeout(resolve,1500));data=await api("/api/job");message("dependency-status",data);} while(data.running);
  }catch(error){message("dependency-status",{ok:false,message:error.message});}
  finally{el("dependencies").disabled=false;}
});
el("install-plugin").addEventListener("click", async () => {
  el("install-plugin").disabled = true;
  try {
    message("plugin-status", await api("/api/action", {action:"install-plugin"}));
    let data; do { await new Promise(resolve=>setTimeout(resolve,1500)); data=await api("/api/job"); message("plugin-status",data); } while(data.running);
    if (data.ok) await refresh();
  } catch(error) { message("plugin-status", {ok:false,message:error.message}); }
  finally { el("install-plugin").disabled=false; }
});
for (const action of ["doctor","restart","stop","open-obs"]) el(action).addEventListener("click",async()=>{
  el(action).disabled=true;el("diagnostics").textContent="Checking device…";
  try{const data=await api("/api/action",{action});el("diagnostics").textContent=data.message+(data.runtime?"\n"+JSON.stringify(data.runtime,null,2):"");}
  catch(error){el("diagnostics").textContent=error.message;}
  finally{el(action).disabled=false;await refreshConnection();}
});
function renderConnection(data) {
  el("connection-status").textContent = `${data.host || "127.0.0.1"}:${data.port || "4457"} · Authentication required\n${data.message || "Connection details unavailable"}`;
  controlCanChange = data.process === "absent" && data.output_known === true;
  updateControlButtons();
}
function updateControlButtons() {
  const confirmed = el("confirm-control-password").checked;
  el("save-control-password").disabled = controlBusy || !controlCanChange || !confirmed;
  el("reset-control-password").disabled = controlBusy || !controlCanChange || !confirmed;
  el("test-connection").disabled = controlBusy;
  el("refresh-connection").disabled = controlBusy;
}
async function refreshConnection() {
  try {renderConnection(await api("/api/connection"));}
  catch(error) {controlCanChange=false;el("connection-status").textContent=error.message;updateControlButtons();}
}
el("refresh-connection").addEventListener("click", refreshConnection);
el("confirm-control-password").addEventListener("change", updateControlButtons);
el("test-connection").addEventListener("click", async () => {
  controlBusy=true;updateControlButtons();
  try {renderConnection(await api("/api/action",{action:"test-connection"}));}
  catch(error) {el("connection-status").textContent=error.message;}
  finally {controlBusy=false;updateControlButtons();}
});
async function changeControlPassword(generate) {
  if (!controlCanChange || controlBusy || !el("confirm-control-password").checked) return;
  const settings={confirm:true,generate,password:generate?"":el("control-password").value};
  controlBusy=true;updateControlButtons();
  try {
    const data=await api("/api/action",{action:"change-obs-password",settings});
    message("control-password-status",data);
    if(data.ok){el("control-password").value="";el("confirm-control-password").checked=false;renderConnection(data);}
  }catch(error){message("control-password-status",{ok:false,message:error.message});}
  finally{settings.password="";controlBusy=false;updateControlButtons();}
}
el("control-password-form").addEventListener("submit",event=>{event.preventDefault();void changeControlPassword(false);});
el("reset-control-password").addEventListener("click",()=>void changeControlPassword(true));
el("close").addEventListener("click",async()=>{const data=await api("/api/action",{action:"close"});window.sessionStorage.removeItem("obsgodSetupToken");document.body.textContent=data.message;});
refresh().catch(error=>{el("diagnostics").textContent=error.message;});

// Advanced workspace commands use the same authenticated local CLI as Gaming
// Mode. Command replies are never treated as proof of streaming/recording.
let workspaceBusy=false,profileCatalog,mediaSnapshot,mediaObservedAt=0,prunePreview;
const workspaceSections=["mixer-heading","profiles-heading","idle-media-heading","media-heading","health-heading"];
function workspaceMessage(id,data){el(id).textContent=typeof data.message==="string"?data.message:"Action completed; confirm actual output state.";el(id).className=data.ok===false?"error":"";}
async function workspaceCall(action,settings,statusId){
  if(workspaceBusy)throw new Error("Another local operation is running. Wait before retrying.");
  workspaceBusy=true;
  cancelMixerTalk();
  const buttons=workspaceSections.flatMap(id=>[...el(id).closest("section").querySelectorAll("button")]);
  const previous=buttons.map(button=>button.disabled);buttons.forEach(button=>button.disabled=true);
  if(statusId)el(statusId).textContent="Checking local settings and output…";
  try{
    const data=await api("/api/action",{action,settings});
    if(statusId)workspaceMessage(statusId,data);
    return data;
  }catch(error){if(statusId)workspaceMessage(statusId,{ok:false,message:error.message});throw error;}
  finally{workspaceBusy=false;buttons.forEach((button,index)=>button.disabled=previous[index]);renderMediaButtons();renderMixer();}
}
function profileFromForm(){
  const [width,height]=el("resolution").value.split("x").map(Number);
  return {version:1,width,height,bitrate:Number(el("bitrate").value),fps:Number(el("fps").value),encoder:el("encoder").value,microphone:el("microphone").checked,capture_mode:el("capture_mode").value};
}
function profileDescription(profile){return profile?`${profile.width}×${profile.height} · ${profile.fps} fps · ${profile.bitrate} kbps · ${profile.encoder}\n${profile.capture_mode==="game"?"Game-only video":"Entire screen, including menus"} · microphone ${profile.microphone?"on":"off"}`:"Settings unavailable";}
function renderProfileCatalog(data){
  profileCatalog=data;
  for(const [id,items,label] of [["profile-preset",data.presets||[],item=>item.label],["profile-saved",data.profiles||[],item=>item.name]]){
    const select=el(id),old=select.value;select.replaceChildren();
    if(!items.length)select.add(new Option("No profiles available",""));
    else for(const item of items)select.add(new Option(label(item),item.name));
    if([...select.options].some(option=>option.value===old))select.value=old;
  }
  el("profile-bindings").textContent=Object.entries(data.game_profiles||{}).map(([game,name])=>`${game} → ${name}`).join("\n")||"No game bindings. Bindings never auto-start output.";
  updatePresetHelp();
}
function updatePresetHelp(){
  const preset=profileCatalog?.presets?.find(item=>item.name===el("profile-preset").value);
  el("profile-preset-help").textContent=preset?`${profileDescription(preset.profile)}\n${preset.description}\nNot hardware-qualified: measure picture, sound, load and battery on your Deck.`:"Load the presets to see their settings and tradeoffs.";
}
async function profileAction(payload){
  const data=await workspaceCall("stream-profiles",payload,"profiles-status");
  if(data.profile)el("profiles-status").textContent+="\n"+profileDescription(data.profile);
  if(data.warnings?.length)el("profiles-status").textContent+="\n"+data.warnings.join("\n");
  if(data.ok&&data.document)el("profile-json").value=JSON.stringify(data.document,null,2);
  if(data.ok&&payload.action==="list")renderProfileCatalog(data);
  return data;
}
function safeWorkspace(handler){return async()=>{try{await handler();}catch{/* The local status field contains the actionable error. */}};}
el("profile-preset").addEventListener("change",updatePresetHelp);
el("profiles-load").addEventListener("click",safeWorkspace(()=>profileAction({action:"list"})));
el("profile-preview").addEventListener("click",safeWorkspace(()=>profileAction({action:"preview",preset:el("profile-preset").value})));
el("profile-apply-preset").addEventListener("click",safeWorkspace(async()=>{const data=await profileAction({action:"apply",preset:el("profile-preset").value});if(data.ok)await refresh();}));
el("profile-apply-saved").addEventListener("click",safeWorkspace(async()=>{const data=await profileAction({action:"apply",name:el("profile-saved").value});if(data.ok)await refresh();}));
el("profile-validate").addEventListener("click",safeWorkspace(()=>profileAction({action:"validate",profile:profileFromForm()})));
el("profile-save").addEventListener("click",safeWorkspace(async()=>{const data=await profileAction({action:"save",name:el("profile-name").value.trim(),profile:profileFromForm()});if(data.ok){const list=await profileAction({action:"list"});if(list.ok)el("profile-saved").value=el("profile-name").value.trim();}}));
el("profile-export").addEventListener("click",safeWorkspace(()=>profileAction({action:"export"})));
el("profile-reset").addEventListener("click",safeWorkspace(async()=>{if(!window.confirm("Reset stream quality, capture and microphone preferences? Your destination, key and media are preserved. This does not start output."))return;const data=await profileAction({action:"reset"});if(data.ok)await refresh();}));
el("profile-import").addEventListener("click",safeWorkspace(async()=>{
  let document;try{document=JSON.parse(el("profile-json").value);}catch{workspaceMessage("profiles-status",{ok:false,message:"Enter valid settings-only JSON first."});return;}
  await profileAction({action:"import",name:el("profile-name").value.trim(),document});
}));
el("profile-bind").addEventListener("click",safeWorkspace(async()=>{const data=await profileAction({action:"bind-game",name:el("profile-saved").value,game_id:el("profile-game").value.trim()});if(data.ok)await profileAction({action:"list"});}));
el("profile-copy").addEventListener("click",async()=>{
  try{await navigator.clipboard.writeText(el("profile-json").value);workspaceMessage("profiles-status",{ok:true,message:"Copied the displayed settings-only JSON."});}
  catch{el("profile-json").focus();el("profile-json").select();workspaceMessage("profiles-status",{ok:false,message:"Clipboard unavailable. The JSON is selected; use Copy manually."});}
});
el("idle-media-form").addEventListener("submit",async event=>{
  event.preventDefault();
  try{
    const data=await workspaceCall("set-idle-media",{idle_style:el("idle-media-kind").value,source:el("idle-media-source").value.trim(),rights_acknowledged:el("idle-media-rights").checked,attribution:el("idle-media-attribution").value.trim()},"idle-media-status");
    if(data.ok){el("idle-media-source").value="";el("idle-media-rights").checked=false;await refresh();}
  }catch{/* Keep input so the owner can correct the problem. */}
});
function renderMediaButtons(){
  const known=mediaSnapshot?.known===true&&Date.now()-mediaObservedAt<8000;
  const recording=mediaSnapshot?.recording?.active===true,replay=mediaSnapshot?.replay_active===true;
  el("record-start").disabled=workspaceBusy||!known||recording;
  el("record-stop").disabled=workspaceBusy||(known&&!recording);
  el("replay-start").disabled=workspaceBusy||!known||replay;
  el("replay-stop").disabled=workspaceBusy||(known&&!replay);
  el("replay-save").disabled=workspaceBusy||!known||!replay;
  el("media-prune-confirm").disabled=workspaceBusy||!prunePreview;
}
function renderMedia(data,updatePreferences=true){
  const snapshot=data.media??data;
  if(typeof snapshot.known!=="boolean")return;
  mediaSnapshot=snapshot;mediaObservedAt=Date.now();
  const storage=snapshot.storage||{};
  const free=typeof storage.available_bytes==="number"?`${(storage.available_bytes/1024**3).toFixed(1)} GiB available`:"Free space unknown";
  el("media-status").textContent=`${snapshot.message||""}\nRecording: ${snapshot.known?(snapshot.recording?.active?"active":"stopped"):"unconfirmed"}\nReplay: ${snapshot.known?(snapshot.replay_active?"active":"stopped"):"unconfirmed"}\n${free}\n${storage.directory||"Recording directory not confirmed"}`;
  const pref=snapshot.preferences;
  if(pref&&updatePreferences){el("media-directory").value=pref.directory||"";el("media-replay-seconds").value=pref.replay_seconds;el("media-replay-memory").value=pref.replay_memory_mb;el("media-reserve").value=pref.reserve_mib;el("media-retention").value=pref.retention_days;}
  renderMediaButtons();
}
async function mediaAction(payload){
  const data=await workspaceCall("media",payload,"media-status");
  if(payload.action==="status")renderMedia(data);
  if(data.recording_path)el("media-status").textContent+="\nSaved: "+data.recording_path;
  if(data.clips){
    const select=el("media-clip");select.replaceChildren();
    for(const clip of data.clips)select.add(new Option(clip.name,clip.name));
    if(!data.clips.length)select.add(new Option("No finalized owned clips",""));
    el("media-library").textContent=data.clips.map(clip=>`${clip.kind} · ${clip.name}\n${(clip.bytes/1024**2).toFixed(1)} MiB · ${clip.modified_utc}`).join("\n\n")||"No finalized owned clips. Existing or interrupted files are preserved outside this list.";
  }
  return data;
}
el("media-refresh").addEventListener("click",safeWorkspace(()=>mediaAction({action:"status"})));
for(const action of ["record-start","record-stop","replay-start","replay-stop","replay-save"]){
  el(action).addEventListener("click",safeWorkspace(async()=>{const result=await mediaAction({action});if(result.ok){const notice=el("media-status").textContent;await mediaAction({action:"status"});el("media-status").textContent=notice+"\n\n"+el("media-status").textContent;}}));
}
el("media-preferences").addEventListener("submit",async event=>{
  event.preventDefault();
  try{const data=await mediaAction({action:"configure",preferences:{version:1,directory:el("media-directory").value.trim(),replay_seconds:Number(el("media-replay-seconds").value),replay_memory_mb:Number(el("media-replay-memory").value),reserve_mib:Number(el("media-reserve").value),retention_days:Number(el("media-retention").value)}});if(data.ok)prunePreview=undefined;}
  catch{/* The operation status explains why no changes were confirmed. */}
});
el("media-list").addEventListener("click",safeWorkspace(()=>mediaAction({action:"list"})));
el("media-export").addEventListener("click",safeWorkspace(()=>mediaAction({action:"export",name:el("media-clip").value,directory:el("media-export-directory").value.trim()})));
el("media-prune-preview").addEventListener("click",safeWorkspace(async()=>{
  const data=await workspaceCall("media",{action:"prune",older_than_days:Number(el("media-retention").value)},"media-prune-status");
  prunePreview=data.ok&&data.clips?.length?data:undefined;el("media-prune-status").textContent+="\n"+JSON.stringify(data.clips??data.candidates??[],null,2);renderMediaButtons();
}));
el("media-prune-confirm").addEventListener("click",safeWorkspace(async()=>{
  if(!prunePreview||!window.confirm("Delete the previewed finalized clips owned by this installation? This cannot be undone. Other media and interrupted files are preserved."))return;
  const days=Number(el("media-retention").value),ids=prunePreview.clips.map(clip=>clip.id);
  prunePreview=undefined;renderMediaButtons();
  await workspaceCall("media",{action:"prune",older_than_days:days,confirm:true,ids},"media-prune-status");
}));
setInterval(renderMediaButtons,1000);
let currentHealth;
function renderHealth(){
  if(!currentHealth)return;
  const now=Date.now(),observed=Date.parse(currentHealth.observed_at||""),expiry=Date.parse(currentHealth.expires_at||"");
  if(!Number.isFinite(observed)||!Number.isFinite(expiry)||observed>now+1000||expiry<=now){el("stream-health-status").textContent="Measurements expired or unavailable. Measure again; no old value is current health.";return;}
  const unit={bitrate_kbps:" kbps",stream_dropped_percent:"% network dropped",encode_skipped_percent:"% encoder skipped",render_missed_percent:"% render missed",cpu_percent:"% CPU",fps:" fps",gpu_percent:"% GPU"};
  const lines=Object.entries(unit).map(([key,suffix])=>{const value=currentHealth.metrics?.[key];return typeof value==="number"&&Number.isFinite(value)&&value>=0?value.toFixed(key==="bitrate_kbps"?0:1)+suffix:`${key}: not measured`;});
  el("stream-health-status").textContent=[currentHealth.message,...lines,`Audio: ${currentHealth.audio||"unknown"}`,`Capture: ${currentHealth.capture||"unknown"}`,...(currentHealth.advice||[]).map(item=>item.message),"Provider/viewer reception: unknown"].join("\n");
}
el("stream-health").addEventListener("click",safeWorkspace(async()=>{currentHealth=await workspaceCall("stream-health",{},"stream-health-status");renderHealth();}));
setInterval(renderHealth,1000);

el("retry-recovery").addEventListener("click",safeWorkspace(()=>workspaceCall("retry-recovery",{},"stream-health-status")));

// Keep visible media/health details current without replacing in-progress form
// edits. Only read-only loopback observations run here; every action still has
// the CLI's own lease and fresh output guard.
let mediaPollPending=false,healthPollPending=false;
function visibleSection(id){const bounds=el(id).closest("section").getBoundingClientRect();return document.visibilityState==="visible"&&bounds.bottom>0&&bounds.top<window.innerHeight;}
setInterval(async()=>{
  if(workspaceBusy||mediaPollPending||!mediaSnapshot||!visibleSection("media-heading"))return;
  mediaPollPending=true;
  try{const data=await api("/api/action",{action:"media",settings:{action:"status"}});renderMedia(data,false);}
  catch{mediaObservedAt=0;renderMediaButtons();}
  finally{mediaPollPending=false;}
},3000);
setInterval(async()=>{
  if(workspaceBusy||healthPollPending||!currentHealth||!visibleSection("health-heading"))return;
  healthPollPending=true;
  try{currentHealth=await api("/api/action",{action:"stream-health",settings:{}});renderHealth();}
  catch{currentHealth={};renderHealth();}
  finally{healthPollPending=false;}
},5000);

// Audio preferences are separate from observed OBS state. This status path is
// read-only: opening the page or reconnecting never enables an input or output.
let mixerSnapshot,mixerPendingPreferences,mixerPolling=false,mixerLevelsDirty=false,mixerOptionsKey="";
const mixerNotices=new Set();
let mixerHeld=false,mixerTalkToken,mixerTalkTimer,mixerTalkWatch,mixerTalkPending=false,mixerTalkEpoch=0;
function mixerFresh(){
  const observed=Date.parse(mixerSnapshot?.observed_at||""),expires=Date.parse(mixerSnapshot?.expires_at||"");
  return mixerSnapshot?.known===true&&mixerSnapshot?.microphone?.known===true&&Number.isFinite(observed)&&Number.isFinite(expires)&&observed<=Date.now()+1000&&expires>Date.now()&&expires>observed&&expires-observed<=15000;
}
function renderMixer(snapshot){
  if(snapshot)mixerSnapshot=snapshot;
  const fresh=mixerFresh(),pref={...(mixerSnapshot?.preferences||{}),...(mixerPendingPreferences||{})},mic=mixerSnapshot?.microphone||{};
  const enabled=pref.microphone_enabled===true,available=mic.available===true,systemMuted=mic.system_muted===true;
  let observed="Microphone state unconfirmed · saved preferences shown below";
  if(fresh&&!enabled)observed="Microphone disabled";
  else if(fresh&&!available)observed="Microphone unavailable · kept muted";
  else if(fresh&&mic.muted===true)observed="Microphone muted on stream";
  else if(fresh&&mic.muted===false)observed=systemMuted?"SteamOS microphone is muted":"Microphone live on stream";
  el("mixer-observed").textContent=workspaceBusy?"Audio change or local operation pending…":observed;
  el("mixer-preference").textContent=`Saved preference: ${pref.microphone_muted===true?"muted":pref.microphone_muted===false?"unmuted":"not loaded"}${pref.push_to_talk?" · hold-to-talk enabled":""}. Reconnecting does not clear a saved mute.`;
  el("mixer-enabled").checked=enabled;el("mixer-ptt").checked=pref.push_to_talk===true;
  const devices=mixerSnapshot?.devices||[],options=[{id:"default",label:"Follow system default · changes stay muted"},...devices.filter(device=>device.id!=="default").map(device=>({id:device.id,label:`${device.label}${device.default?" · current default":""}${device.available===false?" · unavailable":""}`}))];
  if(pref.microphone_device&&pref.microphone_device!=="default"&&!options.some(device=>device.id===pref.microphone_device))options.push({id:pref.microphone_device,label:"Saved input · currently unavailable"});
  const key=JSON.stringify(options);
  if(key!==mixerOptionsKey){el("mixer-device").replaceChildren(...options.map(device=>new Option(device.label,device.id)));mixerOptionsKey=key;}
  el("mixer-device").value=pref.microphone_device||"default";
  if(!mixerLevelsDirty){for(const [id,value] of [["mixer-game-gain",pref.game_gain_percent],["mixer-mic-gain",pref.microphone_gain_percent]])el(id).value=typeof value==="number"&&Number.isFinite(value)&&value>=0&&value<=200?value:100;}
  for(const kind of ["game","mic"])el(`mixer-${kind}-value`).textContent=el(`mixer-${kind}-gain`).value+"%";
  const level=fresh&&available&&!systemMuted&&mic.muted===false&&typeof mic.peak_dbfs==="number"&&Number.isFinite(mic.peak_dbfs)?Math.max(-90,Math.min(0,mic.peak_dbfs)):null;
  const levelText=level===null?"Voice level: not measured":`Voice level: ${level.toFixed(1)} dBFS${mic.signal==="silent"?" · no signal observed":""}`;
  el("mixer-level").value=level??-90;el("mixer-level").setAttribute("aria-valuetext",levelText);el("mixer-level-text").textContent=levelText;
  const blocked=workspaceBusy||controlBusy;
  for(const id of ["mixer-enabled","mixer-device","mixer-game-gain","mixer-mic-gain","mixer-ptt","mixer-refresh"])el(id).disabled=blocked;
  el("mixer-mute").disabled=blocked||!enabled;
  el("mixer-unmute").disabled=blocked||!fresh||!enabled||!available||systemMuted||pref.push_to_talk===true;
  el("mixer-levels").disabled=blocked||!mixerLevelsDirty;
  el("mixer-talk-controls").hidden=!pref.push_to_talk;
  el("mixer-arm").disabled=blocked||!fresh||!enabled||!available||systemMuted||pref.microphone_muted===false;
  el("mixer-talk").disabled=blocked||!fresh||!enabled||!available||systemMuted||!pref.push_to_talk||pref.microphone_muted!==false;
  el("mixer-talk").setAttribute("aria-pressed",String(mixerHeld&&!!mixerTalkToken));
  el("mixer-talk").textContent=mixerHeld&&mixerTalkToken?"Talking lease active · release to mute":"Hold here to talk";
  el("mixer-hardware").textContent=mixerSnapshot?.hardware?.guidance||"";
  const notice=mixerSnapshot?.notice;
  if(notice&&typeof notice.code==="string"&&typeof notice.revision==="string"&&notice.revision&&typeof notice.message==="string"){
    const identity=notice.code+":"+notice.revision;
    if(!mixerNotices.has(identity)){mixerNotices.add(identity);if(mixerNotices.size>100)mixerNotices.delete(mixerNotices.values().next().value);el("mixer-notice").textContent=notice.message;}
  }
  if(el("mixer-talk").disabled&&mixerHeld)cancelMixerTalk();
}
async function readMixer(){
  if(mixerPolling||workspaceBusy)return;
  mixerPolling=true;
  try{const raw=await api("/api/action",{action:"mixer",settings:{action:"status"}}),data=raw.data??raw;renderMixer(data.mixer);}
  catch{if(mixerSnapshot)mixerSnapshot={...mixerSnapshot,known:false};renderMixer();}
  finally{mixerPolling=false;}
}
async function configureMixer(preferences){
  if(workspaceBusy)return;
  mixerPendingPreferences=preferences;
  cancelMixerTalk();
  try{const raw=await workspaceCall("mixer",{action:"configure",preferences},"mixer-status"),data=raw.data??raw;
    if(data.ok&&("game_gain_percent" in preferences||"microphone_gain_percent" in preferences))mixerLevelsDirty=false;
    // Only mixer observations may be taken from this reply. Stream output is
    // never replaced by a preference mutation response.
    if(data.mixer)renderMixer(data.mixer);await readMixer();
  }catch{renderMixer();}
  finally{mixerPendingPreferences=undefined;renderMixer();}
}
for(const kind of ["game","mic"])el(`mixer-${kind}-gain`).addEventListener("input",()=>{mixerLevelsDirty=true;renderMixer();});
el("mixer-levels").addEventListener("click",()=>void configureMixer({game_gain_percent:Number(el("mixer-game-gain").value),microphone_gain_percent:Number(el("mixer-mic-gain").value)}));
el("mixer-enabled").addEventListener("change",()=>void configureMixer({microphone_enabled:el("mixer-enabled").checked,microphone_muted:true}));
el("mixer-device").addEventListener("change",()=>void configureMixer({microphone_device:el("mixer-device").value,microphone_muted:true}));
el("mixer-mute").addEventListener("click",()=>void configureMixer({microphone_muted:true}));
el("mixer-unmute").addEventListener("click",()=>void configureMixer({microphone_muted:false}));
el("mixer-ptt").addEventListener("change",()=>void configureMixer({push_to_talk:el("mixer-ptt").checked,microphone_muted:true}));
el("mixer-arm").addEventListener("click",()=>void configureMixer({microphone_muted:false}));
el("mixer-refresh").addEventListener("click",()=>void readMixer());
function fastMixer(payload,keepalive=false){return fetch("/api/action",{method:"POST",headers:{"Authorization":"Bearer "+token,"Content-Type":"application/json"},body:JSON.stringify({action:"mixer",settings:payload}),cache:"no-store",keepalive}).then(async response=>{const raw=await response.json();if(!response.ok)throw Error(raw.message||"Microphone hold could not be confirmed");return raw.data??raw;});}
function releaseMixerTalk(){
  mixerHeld=false;mixerTalkEpoch++;clearTimeout(mixerTalkTimer);clearTimeout(mixerTalkWatch);const previous=mixerTalkToken;mixerTalkToken=undefined;
  if(previous)void fastMixer({action:"talk-release",token:previous},true).catch(()=>{});renderMixer();
}
function cancelMixerTalk(){const hadLease=mixerHeld||mixerTalkPending||!!mixerTalkToken;releaseMixerTalk();if(hadLease)void fastMixer({action:"talk-cancel"},true).catch(()=>{});}
function watchMixerTalk(milliseconds=1100){clearTimeout(mixerTalkWatch);mixerTalkWatch=setTimeout(()=>{releaseMixerTalk();el("mixer-status").textContent="Talking lease expired or could not be renewed. Mute is unconfirmed until OBS responds.";},milliseconds);}
async function renewMixerTalk(epoch){
  if(!mixerHeld||mixerTalkPending||epoch!==mixerTalkEpoch)return;
  mixerTalkPending=true;
  try{const reply=await fastMixer({action:"talk-start",...(mixerTalkToken?{token:mixerTalkToken}:{})});
    if(!reply.ok||typeof reply.talk_token!=="string"||!reply.talk_token)throw Error(reply.message||"Microphone hold could not be confirmed");
    if(!mixerHeld||epoch!==mixerTalkEpoch){void fastMixer({action:"talk-release",token:reply.talk_token},true).catch(()=>{});return;}
    mixerTalkToken=reply.talk_token;
    const expiry=Date.parse(reply.talk_expires_at||reply.mixer?.talk_expires_at||""),remaining=Number.isFinite(expiry)?expiry-Date.now():(reply.lease_ms||1200);
    if(remaining<=100)throw Error("Talking lease expired before OBS confirmation arrived. Release and try again.");
    watchMixerTalk(Math.max(100,Math.min(1100,remaining-100)));renderMixer();
    mixerTalkTimer=setTimeout(()=>void renewMixerTalk(epoch),Math.min(400,Math.max(100,(reply.lease_ms||1200)/3)));
  }catch(error){if(epoch===mixerTalkEpoch){releaseMixerTalk();el("mixer-status").textContent=error.message;}}
  finally{mixerTalkPending=false;}
}
function pressMixerTalk(){if(mixerHeld||mixerTalkPending||el("mixer-talk").disabled)return;mixerHeld=true;const epoch=++mixerTalkEpoch;watchMixerTalk();void renewMixerTalk(epoch);}
el("mixer-talk").addEventListener("pointerdown",event=>{if(event.button===0){event.preventDefault();el("mixer-talk").setPointerCapture?.(event.pointerId);pressMixerTalk();}});
el("mixer-talk").addEventListener("pointerup",releaseMixerTalk);el("mixer-talk").addEventListener("pointercancel",cancelMixerTalk);
el("mixer-talk").addEventListener("keydown",event=>{if((event.key===" "||event.key==="Enter")&&!event.repeat){event.preventDefault();pressMixerTalk();}});
el("mixer-talk").addEventListener("keyup",event=>{if(event.key===" "||event.key==="Enter"){event.preventDefault();releaseMixerTalk();}});
el("mixer-talk").addEventListener("blur",cancelMixerTalk);window.addEventListener("blur",cancelMixerTalk);window.addEventListener("pagehide",cancelMixerTalk);
document.addEventListener("visibilitychange",()=>{if(document.hidden)cancelMixerTalk();});
el("stop").addEventListener("click",cancelMixerTalk);el("close").addEventListener("click",cancelMixerTalk);
setInterval(()=>{renderMixer();if(!workspaceBusy&&visibleSection("mixer-heading"))void readMixer();},1000);
void readMixer();
