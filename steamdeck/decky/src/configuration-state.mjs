// These destination guides match the existing Desktop setup. They never fetch
// an account key or turn a URL into a credential.
export const providers={
  kick:{name:"Kick",help:"Creator Dashboard → Channel → Stream URL and Key. Copy your own server and key, then set the stream title and category. The URL can be account-specific; prefer RTMPS when provided.",docs:"https://help.kick.com/en/articles/7066931-how-to-stream-on-kick-com",placeholder:"rtmps://your-kick-ingest-server:443/app"},
  twitch:{name:"Twitch",help:"Copy your primary stream key from Twitch Creator Dashboard → Settings → Stream. Use the recommended secure server or another official ingest. Keep the key separate from the server URL.",docs:"https://dev.twitch.tv/docs/video-broadcast/",placeholder:"rtmps://ingest.global-contribute.live-video.net/app",preset:"rtmps://ingest.global-contribute.live-video.net/app"},
  youtube:{name:"YouTube",help:"Enable live streaming and select the intended stream in YouTube Live Control Room. Copy its RTMPS Stream URL and that event's separate stream key. YouTube may also require Go Live; OBS sending bytes does not prove the event is public.",docs:"https://support.google.com/youtube/answer/10364924?hl=en",placeholder:"Copy the RTMPS Stream URL from Live Control Room"},
  custom:{name:"Custom RTMP(S)",help:"Use the server and separate key supplied by your destination. RTMPS encrypts transport; RTMP also supports local/offline workflows. Server URLs cannot contain credentials, query strings or the stream key.",docs:"https://obsproject.com/kb/quick-start-guide",placeholder:"rtmps://your-ingest-server/app"}
};
// Only the fixed public guide inventory can reach Decky's browser navigation.
// Transport errors are deliberately replaced so they cannot echo private data.
export async function openProviderGuide(provider,navigate) {
  if(typeof provider!=="string"||!Object.hasOwn(providers,provider)||typeof navigate!=="function")throw new Error("Could not open the provider setup guide.");
  try{await navigate(providers[provider].docs);}
  catch{throw new Error("Could not open the provider setup guide.");}
}

export const configurationDefaults={version:1,server:"",bitrate:4500,fps:30,encoder:"vaapi",width:1280,height:720,capture_mode:"screen",microphone:false};
export const editableFields=["bitrate","fps","encoder","width","height","capture_mode","microphone"];

const object=value=>!!value&&typeof value==="object"&&!Array.isArray(value);
const booleans=(value,names)=>names.every(name=>typeof value[name]==="boolean");
const publicString=(value,limit)=>typeof value==="string"&&new TextEncoder().encode(value).length<=limit&&!/[\x00-\x1f\x7f-\x9f]/.test(value);
function validServer(server,allowEmpty=false){
  if(!publicString(server,4096))return false;
  // JSON can carry an unpaired surrogate; TextEncoder and URL would replace it.
  for(const character of server){const point=character.codePointAt(0);if(point>=0xd800&&point<=0xdfff)return false;}
  if(!server)return allowEmpty;
  // URL normalizes empty userinfo away. Go rejects any authority userinfo,
  // while an @ in the path remains an ordinary destination path character.
  if(server.match(/^[^:]+:\/\/([^/?#]*)/)?.[1].includes("@"))return false;
  try{const url=new URL(server);return ["rtmp:","rtmps:"].includes(url.protocol)&&!!url.hostname&&!url.username&&!url.password&&!url.search&&!url.hash;}
  catch{return false;}
}

// Draft defaults are useful before a read, but never establish readiness.
// Validate the complete public schema before projecting only named fields.
export function validConfiguration(value){
  if(!object(value)||value.schema_version!==1||!booleans(value,["ok","configured","key_configured","output_known","can_configure","can_close"])||typeof value.message!=="string")return false;
  const settings=value.settings,connection=value.connection;
  if(!object(settings)||settings.version!==1||!validServer(settings.server,true)||
      !Number.isInteger(settings.bitrate)||settings.bitrate<1000||settings.bitrate>8000||
      ![30,60].includes(settings.fps)||!["vaapi","x264"].includes(settings.encoder)||typeof settings.microphone!=="boolean")return false;
  if(value.configured!==value.key_configured||(value.configured&&!settings.server))return false;
  if("capture_mode" in settings&&!["","screen","game"].includes(settings.capture_mode))return false;
  const hasWidth="width" in settings,hasHeight="height" in settings;
  if(hasWidth!==hasHeight)return false;
  if(hasWidth&&(!Number.isInteger(settings.width)||!Number.isInteger(settings.height)||
      !["0x0","960x540","1280x720","1920x1080"].includes(`${settings.width}x${settings.height}`)))return false;
  if(!object(connection)||!booleans(connection,["ok","authentication_required","credentials_available","connected","managed","output_known"])||
      !["127.0.0.1","localhost","::1"].includes(connection.host)||connection.port!=="4457"||
      connection.authentication_required!==true||!["absent","running","unknown"].includes(connection.process)||
      !["stopped","streaming","recording","unknown","setup"].includes(connection.state)||typeof connection.message!=="string"||
      ("awaiting_verification" in connection&&typeof connection.awaiting_verification!=="boolean"))return false;
  if(value.can_configure&&value.can_close)return false;
  if((value.can_configure||value.can_close)&&(!value.ok||!value.output_known))return false;
  if(value.can_configure&&(connection.process!=="absent"||!connection.output_known||connection.connected||connection.managed||!["stopped","setup"].includes(connection.state)))return false;
  // The nested presence-only observation may be unknown while the separate
  // runtime observation confirms that running managed OBS is idle.
  if(value.can_close&&(connection.process!=="running"||["streaming","recording"].includes(connection.state)))return false;
  return true;
}

export function publicConfiguration(value){
  if(!validConfiguration(value))return undefined;
  const connection=value.connection;
  const result={schema_version:1,ok:value.ok,configured:value.configured,key_configured:value.key_configured,
    settings:configurationDraft(value.settings),output_known:value.output_known,can_configure:value.can_configure,can_close:value.can_close,message:value.message,
    connection:{ok:connection.ok,host:connection.host,port:connection.port,authentication_required:connection.authentication_required,
      credentials_available:connection.credentials_available,connected:connection.connected,managed:connection.managed,process:connection.process,
      output_known:connection.output_known,state:connection.state,message:connection.message,
      ...(typeof connection.awaiting_verification==="boolean"?{awaiting_verification:connection.awaiting_verification}:{})}};
  if(object(value.action_result)&&typeof value.action_result.ok==="boolean"&&typeof value.action_result.message==="string")
    return {...result,action_result:{id:value.action_result.id,action:value.action_result.action,ok:value.action_result.ok,message:value.action_result.message}};
  return result;
}

export function inferredProvider(server) {
  try{
    const host=new URL(server).hostname.toLowerCase();
    if(host==="ingest.global-contribute.live-video.net"||host.endsWith(".contribute.live-video.net")||host.endsWith(".twitch.tv"))return "twitch";
    if(["a.rtmps.youtube.com","b.rtmps.youtube.com","a.rtmp.youtube.com","b.rtmp.youtube.com"].includes(host))return "youtube";
    if(host.endsWith(".global-contribute.live-video.net"))return "kick";
  }catch{/* Unknown destinations use the explicit custom guide. */}
  return "custom";
}

export function configurationDraft(settings) {
  const draft={...configurationDefaults};
  for(const name of ["server",...editableFields])if(settings?.[name]!==undefined)draft[name]=settings[name];
  // Zero dimensions are the existing legacy representation of 720p.
  if(!draft.width&&!draft.height){draft.width=1280;draft.height=720;}
  if(!draft.capture_mode)draft.capture_mode="screen";
  return draft;
}

export function destinationChanged(saved,provider,server) {
  const oldProvider=providers[saved?.provider]?saved.provider:saved?.configured?inferredProvider(saved?.settings?.server??""):"kick";
  return provider!==oldProvider||server.trim()!==(saved?.settings?.server??"");
}

export function validateDestination(saved,provider,draft,key,replaceKey=false) {
  if(!providers[provider])return "Choose a supported destination guide.";
  const server=draft.server.trim();
  if(!validServer(server))return "Enter the RTMP(S) server URL from your dashboard without a username, query or key. Put the stream key in its separate field.";
  const secret=key.trim();
  if(!secret&&(!saved?.configured||replaceKey||destinationChanged(saved,provider,server)))return "Enter the key for this destination. A saved key can be kept only for the same provider and server.";
  if(new TextEncoder().encode(secret).length>4096||/[\r\n\0]/.test(secret))return "Enter a valid stream key of at most 4096 bytes without line breaks.";
  if(!Number.isInteger(draft.bitrate)||draft.bitrate<1000||draft.bitrate>8000)return "Choose a video bitrate from 1000 to 8000 kbps.";
  if(![30,60].includes(draft.fps))return "Choose 30 or 60 frames per second.";
  if(!["vaapi","x264"].includes(draft.encoder))return "Choose the hardware or software H.264 encoder.";
  if(!["960x540","1280x720","1920x1080"].includes(`${draft.width}x${draft.height}`))return "Choose a supported output resolution.";
  if(!["screen","game"].includes(draft.capture_mode))return "Choose screen or game-only capture.";
  return "";
}

// Send only intentional edits for an existing configuration. The backend owns
// merging the complete settings through Go Configure, including idle media and
// advanced fields this form does not edit. Secrets are never read into a draft.
export function configurationPayload(saved,provider,draft,key,edited,replaceKey=false) {
  /** @type {Record<string, unknown>} */
  const payload={};
  if(!saved?.configured||draft.server.trim()!==(saved?.settings?.server??""))payload.server=draft.server.trim();
  if(key.trim())payload.stream_key=key.trim();
  const oldProvider=providers[saved?.provider]?saved.provider:saved?.configured?inferredProvider(saved?.settings?.server??""):"kick";
  if(replaceKey||provider!==oldProvider)payload.replace_key=true;
  for(const name of editableFields)if(!saved?.configured||edited[name])payload[name]=draft[name];
  return payload;
}

export function configurationControls(status,observedAt,now,{busy=false}={}) {
  const fresh=validConfiguration(status)&&now>=observedAt&&now-observedAt<=20000;
  const canConfigure=fresh&&status.ok===true&&status.output_known===true&&status.can_configure===true&&!busy;
  const canChangePassword=canConfigure&&status.configured===true&&status.connection?.process==="absent"&&status.connection?.output_known===true;
  return {fresh,canConfigure,canChangePassword,
    canClose:fresh&&status.ok===true&&status.output_known===true&&status.can_close===true&&!busy,
    canTest:fresh&&!busy,
    reason:busy?"Wait for the current operation to finish.":!fresh?"Configuration readiness is unconfirmed. Refresh settings before making changes.":
      !canConfigure?status.message||"Stop every output and close managed OBS before changing settings.":"Saving settings does not start OBS or broadcast."};
}

export function validateControlPassword(password) {
  const bytes=new TextEncoder().encode(password).length;
  return bytes<12||bytes>128||/[\x00-\x1f\x7f-\x9f]/.test(password)?"Use a local control password of 12–128 bytes without control characters.":"";
}
