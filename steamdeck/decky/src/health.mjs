// Shared by the panel and the tab icon; a failed poll never becomes "Stopped".
export function health(result, lastProgress, now) {
  if (!result) return {label:"Checking OBS…", color:"#f5c56b", live:false};
  if (result.state === "setup") return {label:"Setup required", color:"#f5c56b", live:false};
  if (!result.ok || result.state === "unknown" || result.state === "error") return {label:"Check OBS", color:"#f5c56b", live:false};
  if (result.stream?.active) {
    if (result.stream.reconnecting || result.stream.bytes <= 0 || now-lastProgress > 7000) return {label:"Connecting / stalled", color:"#f5c56b", live:false};
    return {label:"OBS streaming", color:"#6ded9c", live:true};
  }
  return {label:"Stopped", color:"#f47c7c", live:false};
}
