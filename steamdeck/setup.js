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
  if (data.product_name) {el("product-name").textContent = "● " + data.product_name;document.title = data.product_name + " · Steam Deck setup";}
  if (data.settings) {
    for (const id of ["server", "bitrate", "fps", "encoder"]) el(id).value = data.settings[id];
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
  const settings = {version:1, server:el("server").value.trim(), stream_key:el("key").value.trim(), bitrate:Number(el("bitrate").value), fps:Number(el("fps").value), encoder:el("encoder").value, microphone:el("microphone").checked, capture_mode:el("capture_mode").value, idle_style:el("idle_style").value, idle_text:el("idle_text").value};
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
