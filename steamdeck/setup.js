"use strict";
const fragment = window.location.hash.slice(1);
if (fragment) window.sessionStorage.setItem("obsgodSetupToken", fragment);
const token = fragment || window.sessionStorage.getItem("obsgodSetupToken") || "";
window.history.replaceState(null, "", "/");
const el = (id) => document.getElementById(id);
async function api(path, body) {
  const response = await fetch(path, {method: body ? "POST" : "GET", headers: {"Authorization": "Bearer " + token, "Content-Type": "application/json"}, body: body ? JSON.stringify(body) : undefined, cache: "no-store"});
  const data = await response.json();
  if (!response.ok) throw new Error(data.message || "Setup connection failed");
  return data;
}
function message(id, data) { el(id).textContent = data.message; el(id).className = data.ok === false ? "error" : "success"; }
async function refresh() {
  const data = await api("/api/status");
  if (data.settings) {
    for (const id of ["server", "bitrate", "fps", "encoder"]) el(id).value = data.settings[id];
    el("microphone").checked = data.settings.microphone;
  }
  if (data.configured) el("key").placeholder = "Saved securely · leave blank to keep";
  el("zip-path").textContent = data.plugin_zip;
  el("decky-status").textContent = data.decky_status?.message || "Decky service readiness has not been verified.";
  if (!data.flatpak) message("dependency-status", {ok:false,message:"Flatpak was not found. This installer is intended for SteamOS / Steam Deck."});
}
el("settings").addEventListener("submit", async (event) => {
  event.preventDefault(); el("save").disabled = true;
  const settings = {version:1, server:el("server").value.trim(), stream_key:el("key").value.trim(), bitrate:Number(el("bitrate").value), fps:Number(el("fps").value), encoder:el("encoder").value, microphone:el("microphone").checked};
  try {const data=await api("/api/action", {action:"configure",settings});message("save-status", data);if(data.ok){el("key").value="";el("key").placeholder="Saved securely · leave blank to keep";}}
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
  finally{el(action).disabled=false;}
});
el("close").addEventListener("click",async()=>{const data=await api("/api/action",{action:"close"});window.sessionStorage.removeItem("obsgodSetupToken");document.body.textContent=data.message;});
refresh().catch(error=>{el("diagnostics").textContent=error.message;});
