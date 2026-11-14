// These destination guides match the existing Desktop setup. They never fetch
// an account key or turn a URL into a credential.
export const providers={
  kick:{name:"Kick",help:"Creator Dashboard → Channel → Stream URL and Key. Copy your own server and key, then set the stream title and category. The URL can be account-specific; prefer RTMPS when provided.",docs:"https://help.kick.com/en/articles/7066931-how-to-stream-on-kick-com",placeholder:"rtmps://your-kick-ingest-server:443/app"},
  twitch:{name:"Twitch",help:"Copy your primary stream key from Twitch Creator Dashboard → Settings → Stream. Use the recommended secure server or another official ingest. Keep the key separate from the server URL.",docs:"https://dev.twitch.tv/docs/video-broadcast/",placeholder:"rtmps://ingest.global-contribute.live-video.net/app",preset:"rtmps://ingest.global-contribute.live-video.net/app"},
  youtube:{name:"YouTube",help:"Enable live streaming and select the intended stream in YouTube Live Control Room. Copy its RTMPS Stream URL and that event's separate stream key. YouTube may also require Go Live; OBS sending bytes does not prove the event is public.",docs:"https://support.google.com/youtube/answer/10364924?hl=en",placeholder:"Copy the RTMPS Stream URL from Live Control Room"},
  custom:{name:"Custom RTMP(S)",help:"Use the server and separate key supplied by your destination. RTMPS encrypts transport; RTMP also supports local/offline workflows. Server URLs cannot contain credentials, query strings or the stream key.",docs:"https://obsproject.com/kb/quick-start-guide",placeholder:"rtmps://your-ingest-server/app"}
};
export const configurationDefaults={server:"",bitrate:4500,fps:30,encoder:"vaapi",width:1280,height:720,capture_mode:"screen",microphone:false};
export const editableFields=["bitrate","fps","encoder","width","height","capture_mode","microphone"];

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
  try{
    const url=new URL(server);
    if(!["rtmp:","rtmps:"].includes(url.protocol)||!url.hostname||url.username||url.password||url.search||url.hash||/[\r\n\0]/.test(server))throw Error();
  }catch{return "Enter the RTMP(S) server URL from your dashboard without a username, query or key. Put the stream key in its separate field.";}
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
  const fresh=!!status&&status.schema_version===1&&now>=observedAt&&now-observedAt<=20000;
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
