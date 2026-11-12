(async () => {
  "use strict";
  const request = __OBSGOD_REQUEST__;
  const answer = (value) => JSON.stringify(value);
  const backend = window.DeckyBackend;
  if (!backend || backend.ws?.readyState !== 1) return answer({ok:false,code:"no-frontend"});
  if (typeof backend.call !== "function" || typeof backend.addEventListener !== "function" ||
      typeof backend.removeEventListener !== "function" || !(backend.eventListeners instanceof Map)) {
    return answer({ok:false,code:"unsupported"});
  }
  const bounded = (promise, milliseconds = 8000) => {
    let timer;
    return Promise.race([promise, new Promise((_, reject) => {timer = setTimeout(() => reject(new Error("timeout")), milliseconds);})])
      .finally(() => clearTimeout(timer));
  };
  let version, plugins;
  try {
    const info = await bounded(backend.call("updater/get_version_info"));
    version = info?.current;
    if (typeof version !== "string" || !/^v?3\.[0-9]+\.[0-9]+(?:-[A-Za-z0-9.-]+)?$/.test(version)) {
      return answer({ok:false,code:"unsupported"});
    }
    plugins = await bounded(backend.call("loader/get_plugins"));
    if (!Array.isArray(plugins)) return answer({ok:false,code:"probe-failed"});
    if (request.operation === "probe") return answer({ok:true,decky_version:version,frontend_connected:true});
  } catch (_) { return answer({ok:false,code:"probe-failed"}); }

  // Use Decky's existing frontend transport. Opening a second /ws connection
  // would disconnect Steam and races WSRouter's single-socket cleanup in 3.3.1.
  if (window.__obsgodInstallerRunning) return answer({ok:false,code:"busy"});
  const operation = {};
  window.__obsgodInstallerRunning = operation;
  const pendingMutations = new Set();
  let finished = false;
  const release = () => {
    if (finished && pendingMutations.size === 0 && window.__obsgodInstallerRunning === operation) {
      delete window.__obsgodInstallerRunning;
    }
  };
  const mutate = (route, ...args) => {
    // A UI/HTTP timeout does not cancel Decky's original call. Keep ownership
    // until that actual mutation settles, including after this script returns.
    const pending = Promise.resolve(backend.call(route, ...args));
    pendingMutations.add(pending);
    const settled = () => { pendingMutations.delete(pending); release(); };
    pending.then(settled, settled);
    return pending;
  };
  if (request.operation === "uninstall") {
    try {
      // Fixed compatibility identity; no caller-supplied plugin name or path.
      // Decky 3.3.1 may swallow filesystem errors, so verify resulting state.
      const loaded = plugins.some(plugin => plugin?.name === "OBSGod");
      if (loaded && request.uninstall_existing !== true) {
        return answer({ok:false,code:"uninstall-location-unconfirmed"});
      }
      if (request.uninstall_existing === true) {
        await bounded(mutate("utilities/uninstall_plugin", "OBSGod"), 60000);
      }
      const remaining = await bounded(backend.call("loader/get_plugins"));
      if (!Array.isArray(remaining) || remaining.some(plugin => plugin?.name === "OBSGod")) throw new Error("still-installed");
      const order = await bounded(backend.call("utilities/settings/get", "pluginOrder", []));
      if (!Array.isArray(order) || !order.every(name => typeof name === "string")) throw new Error("order");
      const updated = order.filter(name => name !== "OBSGod");
      if (JSON.stringify(updated) !== JSON.stringify(order)) {
        await bounded(mutate("utilities/settings/set", "pluginOrder", updated));
      }
      return answer({ok:true,removed:true,decky_version:version,frontend_connected:backend.ws?.readyState === 1});
    } catch (_) { return answer({ok:false,code:"uninstall-unconfirmed"}); }
    finally { finished = true; release(); }
  }
  const event = "loader/add_plugin_install_prompt";
  const original = Array.from(backend.eventListeners.get(event) || []);
  let prompt = "";
  let filtered = false;
  const owned = (name, candidate, id, digest, kind) => name === "OBSGod" && candidate === request.version &&
    digest === request.sha256 && kind === 4 && typeof id === "string" && id.length > 0 && id.length < 128;
  const listener = (...args) => {
    if (owned(...args)) { if (!prompt) prompt = args[2]; return; }
    // Unrelated install prompts retain their original UI and approval behavior.
    for (const previous of original) Promise.resolve().then(() => previous(...args)).catch(() => {});
  };
  try {
    const order = await bounded(backend.call("utilities/settings/get", "pluginOrder", []));
    if (!Array.isArray(order) || !order.every(value => typeof value === "string")) throw new Error("order");
    for (const previous of original) backend.removeEventListener(event, previous);
    backend.addEventListener(event, listener);
    filtered = true;
    await bounded(backend.call("utilities/install_plugin", "file://" + request.zip_path, "OBSGod", request.version, request.sha256, 4));
    if (!prompt) throw new Error("prompt");
    await bounded(mutate("utilities/confirm_plugin_install", prompt), 60000);
    const plugins = await bounded(backend.call("loader/get_plugins"));
    if (!Array.isArray(plugins) || !plugins.some(plugin => plugin?.name === "OBSGod" && plugin.version === request.version &&
        plugin.disabled === false && plugin.load_type === 1)) throw new Error("version");
    const current = await bounded(backend.call("utilities/settings/get", "pluginOrder", []));
    if (!Array.isArray(current) || !current.every(value => typeof value === "string")) throw new Error("order");
    const position = order.indexOf("OBSGod");
    const updated = current.filter(name => name !== "OBSGod");
    updated.splice(position < 0 ? updated.length : Math.min(position, updated.length), 0, "OBSGod");
    if (JSON.stringify(updated) !== JSON.stringify(current)) {
      await bounded(mutate("utilities/settings/set", "pluginOrder", updated));
    }
    return answer({ok:true,version:request.version,decky_version:version,frontend_connected:backend.ws?.readyState === 1});
  } catch (_) { return answer({ok:false,code:"install-unconfirmed"}); }
  finally {
    if (filtered) {
      backend.removeEventListener(event, listener);
      for (const previous of original) backend.addEventListener(event, previous);
    }
    finished = true;
    release();
  }
})()
