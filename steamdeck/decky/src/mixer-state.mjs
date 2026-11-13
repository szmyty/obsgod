// Local mixer preferences do not establish what OBS is actually capturing.
// Expired observations are unknown; in particular, they never authorize Unmute.
export function mixerFresh(mixer, now = Date.now()) {
  if (!mixer || mixer.known !== true) return false;
  const observed = Date.parse(mixer.observed_at ?? "");
  const expires = Date.parse(mixer.expires_at ?? "");
  return Number.isFinite(observed) && Number.isFinite(expires) && observed <= now + 1000 &&
    expires > now && expires > observed && expires - observed <= 15000;
}

export function mixerView(mixer, busy = false, now = Date.now()) {
  const preferences = mixer?.preferences ?? {};
  const microphone = mixer?.microphone ?? {};
  const fresh = mixerFresh(mixer, now) && microphone.known === true;
  const enabled = preferences.microphone_enabled === true;
  const available = microphone.available === true;
  const systemMuted = microphone.system_muted === true;
  const actualMuted = fresh && typeof microphone.muted === "boolean" ? microphone.muted : undefined;
  let label = "Microphone state unconfirmed";
  if (fresh && !enabled) label = "Microphone disabled";
  else if (fresh && !available) label = "Microphone unavailable · kept muted";
  else if (actualMuted === true) label = "Microphone muted on stream";
  else if (actualMuted === false) label = systemMuted ? "SteamOS microphone is muted" : "Microphone live on stream";
  const canUnmute = fresh && enabled && available && !systemMuted && !busy;
  const level = fresh && available && actualMuted === false && !systemMuted &&
    typeof microphone.peak_dbfs === "number" && Number.isFinite(microphone.peak_dbfs)
    ? Math.max(-90, Math.min(0, microphone.peak_dbfs)) : undefined;
  return {
    fresh, preferences, microphone, enabled, available, systemMuted, actualMuted, label,
    muteDisabled: !!busy || !enabled,
    unmuteDisabled: !canUnmute || preferences.push_to_talk === true,
    talkDisabled: !canUnmute || preferences.push_to_talk !== true || preferences.microphone_muted === true,
    settingsDisabled: !!busy,
    level,
    levelText: level === undefined ? "Voice level: not measured" : `Voice level: ${level.toFixed(1)} dBFS`,
  };
}

export function mixerNotice(mixer, seen) {
  const notice = mixer?.notice;
  if (!notice || typeof notice.code !== "string" || typeof notice.revision !== "string" ||
      !notice.revision || typeof notice.message !== "string") return undefined;
  const key = `${notice.code}:${notice.revision}`;
  if (seen.has(key)) return undefined;
  seen.add(key);
  // Bound the process-lifetime de-duplication memory without restoring old
  // device identifiers or storing private input labels in a toast history.
  if (seen.size > 100) seen.delete(seen.values().next().value);
  return {key, code: notice.code, message: notice.message};
}

export function mixerGain(value, fallback = 100) {
  return typeof value === "number" && Number.isFinite(value) && value >= 0 && value <= 200 ? value : fallback;
}
