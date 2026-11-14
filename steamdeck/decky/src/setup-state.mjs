// Dependency readiness is separate from OBS listener and output readiness.
// A Later preference never records successful installation.
const laterKey="obsgod.dependency-setup.later";
const states=new Set(["setup_required","ready","running","cancelling","cancelled","interrupted","failed"]);
export const dependencyFreshness=20000;

export function createDependencyView() {
  return {status:undefined,lastObserved:0,latestRequest:0,epoch:0,unavailable:false};
}

export function observeDependencies(view,next,now,request,epoch) {
  if(epoch!==view.epoch||request<view.latestRequest)return false;
  if(next?.schema_version!==1||!states.has(next.state)||typeof next.ready!=="boolean")return false;
  view.status=next;
  view.lastObserved=now;
  view.latestRequest=request;
  view.unavailable=false;
  return true;
}

export function dependencyObservationFailed(view,request,epoch) {
  if(epoch!==view.epoch||request<view.latestRequest)return false;
  view.latestRequest=request;
  view.unavailable=true;
  return true;
}

export function dependencyView(view,now,action="") {
  const status=view.status;
  const fresh=!!status&&!view.unavailable&&now>=view.lastObserved&&now-view.lastObserved<=dependencyFreshness;
  const state=fresh?status.state:"unknown";
  const ready=fresh&&state==="ready"&&status.ready===true;
  const running=state==="running"||state==="cancelling";
  const reason=!fresh?"Dependency readiness is unconfirmed. Check setup status before starting.":
    ready?"OBS and its compatible GStreamer extension are installed. This does not start OBS or a stream.":
    status.reason?.message||status.message||"Set up the required OBS dependencies before starting.";
  return {ready,state,reason,busy:!!action||running,
    canInstall:fresh&&!ready&&!running&&!action&&status.can_install===true,
    canCancel:fresh&&state==="running"&&!action&&status.can_cancel===true,
    title:ready?"Dependencies ready":running?state==="cancelling"?"Cancelling setup…":"Installing dependencies…":
      !fresh?view.unavailable?"Setup status unavailable":status?"Check dependency setup":"Checking dependencies…":"Setup required"};
}

export function dependencyConsent(status) {
  const dependencies=Array.isArray(status?.dependencies)?status.dependencies:[];
  const missing=dependencies.filter(item=>item.installed!==true||item.compatible!==true);
  const lines=missing.map(item=>item.id==="obs"?"OBS Studio (user Flatpak), with its bundled WebSocket server":
    item.id==="gstreamer"?"The GStreamer extension compatible with your OBS Flatpak":item.name||"Required Flatpak dependency");
  if(status?.remote?.needs_add===true)lines.unshift("The official Flathub remote for your user account");
  return lines;
}

export function readSetupLater(storage) {
  try{return storage?.getItem(laterKey)==="1";}catch{return false;}
}

export function rememberSetupLater(storage,later) {
  try{if(later)storage?.setItem(laterKey,"1");else storage?.removeItem(laterKey);}catch{/* Private browsing/storage denial must not prevent setup. */}
}
