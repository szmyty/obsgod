// UI gates supplement backend leases and fresh OBS checks; they never authorize
// output themselves. Unknown replay state must not look like an idle recorder.
export function mediaControls(result, busy = false) {
  const media = result?.media;
  const absent = result?.process === "absent" && result?.output_known === true;
  const known = result?.output_known === true && (media?.known === true || absent);
  const recording = media?.recording?.active === true || result?.recording === true;
  const replay = media?.replay_active === true;
  const operation = !!busy || !!result?.operation;
  const ready = known && !!result?.configured && !operation;
  return {
    known, recording, replay,
    idle: known && !recording && !replay && !result?.stream?.active && !operation,
    recordStartDisabled: !ready || recording,
    recordStopDisabled: operation || (known && !recording),
    replayStartDisabled: !ready || replay,
    replayStopDisabled: operation || (known && !replay),
    replaySaveDisabled: !ready || !replay,
  };
}

export function healthFresh(report, now = Date.now()) {
  const observed = Date.parse(report?.observed_at ?? "");
  const expires = Date.parse(report?.expires_at ?? "");
  return Number.isFinite(observed) && Number.isFinite(expires) && observed <= now + 1000 && expires > now && expires > observed;
}

export function metricText(report, key, unit, now = Date.now(), digits = 1) {
  const value = report?.metrics?.[key];
  if (!healthFresh(report, now) || typeof value !== "number" || !Number.isFinite(value) || value < 0) return "Not measured";
  return `${value.toFixed(digits)}${unit}`;
}

export function profileSummary(profile) {
  if (!profile) return "Settings not loaded";
  return `${profile.width}×${profile.height} · ${profile.fps} fps · ${profile.bitrate} kbps · ${profile.encoder === "vaapi" ? "hardware H.264" : "software H.264"}\n${profile.capture_mode === "game" ? "Game-only video" : "Entire screen, including menus"} · microphone ${profile.microphone ? "on" : "off"}`;
}
