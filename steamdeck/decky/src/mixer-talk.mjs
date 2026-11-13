// A panel-local press is a short renewable lease, never a global Steam chord.
// Releasing while acquisition is in flight still releases the returned token.
/** @param {(payload: Record<string, unknown>) => Promise<any>} request
 * @param {(active: boolean) => void} changed
 * @param {(message: string) => void} failed */
export function createTalkLease(request, changed = (_active) => {}, failed = (_message) => {}) {
  let held = false, token, timer, watchdog, disposed = false, inFlight = false, generation = 0;
  function clear() {
    if (timer !== undefined) clearTimeout(timer);
    if (watchdog !== undefined) clearTimeout(watchdog);
    timer = watchdog = undefined;
  }
  function watch(milliseconds = 1100) {
    if (watchdog !== undefined) clearTimeout(watchdog);
    watchdog = setTimeout(() => {
      release(); failed("Talking lease expired or could not be renewed. Microphone mute is unconfirmed until OBS responds.");
    }, milliseconds);
  }
  async function releaseToken(value) {
    if (value) try { await request({action: "talk-release", token: value}); } catch { /* expiry is the fallback */ }
  }
  async function renew(epoch) {
    if (!held || disposed || inFlight || epoch !== generation) return;
    inFlight = true;
    try {
      const raw = await request({action: "talk-start", ...(token ? {token} : {})});
      const reply = raw?.data ?? raw;
      if (!reply?.ok || typeof reply.talk_token !== "string" || !reply.talk_token) throw new Error(reply?.message || "Microphone hold could not be confirmed. Release and try again.");
      const acquired = reply.talk_token;
      if (!held || disposed || epoch !== generation) { await releaseToken(acquired); return; }
      token = acquired;
      const expiry = Date.parse(reply.talk_expires_at ?? reply.mixer?.talk_expires_at ?? "");
      const remaining = Number.isFinite(expiry) ? expiry - Date.now() : (reply.lease_ms || 1200);
      if (remaining <= 100) throw new Error("Talking lease expired before OBS confirmation arrived. Release and try again.");
      watch(Math.max(100, Math.min(1100, remaining - 100)));
      changed(true);
      timer = setTimeout(() => { timer = undefined; void renew(epoch); }, Math.min(400, Math.max(100, (reply.lease_ms || 1200) / 3)));
    } catch (error) {
      if (epoch === generation) {
        held = false; clear(); const previous = token; token = undefined;
        changed(false); failed(error instanceof Error ? error.message : "Microphone hold could not be confirmed.");
        void releaseToken(previous);
      }
    } finally { inFlight = false; }
  }
  function release() {
    held = false; generation++; clear(); const previous = token; token = undefined;
    changed(false); void releaseToken(previous);
  }
  return {
    press() { if (disposed || held || inFlight) return; held = true; const epoch = ++generation; watch(); void renew(epoch); },
    release,
    cancel() { release(); void request({action: "talk-cancel"}).catch(() => {}); },
    dispose() { disposed = true; release(); void request({action: "talk-cancel"}).catch(() => {}); },
  };
}
