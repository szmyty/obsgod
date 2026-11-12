const assert = require("node:assert/strict");
let source = "";
process.stdin.setEncoding("utf8");
process.stdin.on("data", value => {source += value;});
process.stdin.on("end", async () => {
  const mode = process.env.OBSGOD_TRANSPORT_TEST_MODE;
  const event = "loader/add_plugin_install_prompt";
  const digest = "a".repeat(64);
  let order = ["Alpha", "OBSGod", "Beta"];
  let confirms = 0;
  let uninstalls = 0;
  let removed = mode === "uninstall-empty" || mode === "uninstall-orphan";
  let orphanFolder = mode === "uninstall-orphan";
  let pendingConfirmation;
  let settleConfirmation;
  if (mode === "confirm-timeout" || mode === "confirm-timeout-reject" || mode === "uninstall-timeout") {
    // Exercise the actual timeout path without a one-minute test delay.
    const originalSetTimeout = global.setTimeout;
    global.setTimeout = (callback, milliseconds, ...args) => originalSetTimeout(callback, Math.min(milliseconds, 5), ...args);
    pendingConfirmation = new Promise((resolve, reject) => {
      settleConfirmation = mode === "confirm-timeout-reject" ? reject : resolve;
    });
  }
  const prompts = [];
  const original = (...args) => {prompts.push(args[0]);};
  const listeners = new Map([[event, new Set([original])]]);
  const socket = {readyState: mode === "no-frontend" ? 3 : 1};
  const backend = {
    ws: socket, eventListeners: listeners,
    addEventListener(name, listener) {if (!listeners.has(name)) listeners.set(name,new Set()); listeners.get(name).add(listener);},
    removeEventListener(name, listener) {listeners.get(name)?.delete(listener); if (listeners.get(name)?.size===0) listeners.delete(name);},
    async call(route,...args) {
      if (route === "updater/get_version_info") return {current:"v3.3.1"};
      if (route === "loader/get_plugins") return removed ? [{name:"Other",version:"9"}] : [{name:"OBSGod",version:"0.1.0-test",disabled:false,load_type:1},{name:"Other",version:"9"}];
      if (route === "utilities/settings/get") return [...order];
      if (route === "utilities/settings/set") {order=args[1];return;}
      if (route === "utilities/uninstall_plugin") {
        assert.deepEqual(args,["OBSGod"]); uninstalls++;
        if (mode === "uninstall-reject") throw Error("fixture-secret do not expose");
        if (pendingConfirmation) await pendingConfirmation;
        if (mode === "uninstall-orphan" && uninstalls === 1) return;
        orphanFolder = false;
        if (mode !== "uninstall-retained") {removed=true;order=["Alpha","Beta"];}
        return;
      }
      if (route === "utilities/install_plugin") {
        assert.deepEqual(args,["file:///home/deck/space and %20/plugin.zip","OBSGod","0.1.0-test",digest,4]);
        for (const listener of listeners.get(event)) listener("Other","9.9.9","unrelated-request",digest,4);
        if (mode !== "missing-prompt") for (const listener of listeners.get(event)) listener("OBSGod","0.1.0-test","expected-request",digest,4);
        return;
      }
      if (route === "utilities/confirm_plugin_install") {
        assert.deepEqual(args,["expected-request"]); confirms++;
        if (mode === "reject") throw Error("fixture-secret do not expose");
        if (pendingConfirmation && confirms === 1) await pendingConfirmation;
        order=["Alpha","Beta"];
        return;
      }
      throw Error("unexpected route");
    }
  };
  global.window={DeckyBackend:backend};
  const result = JSON.parse(await eval(source));
  assert.equal(backend.ws,socket,"Steam frontend connection replaced");
  assert.deepEqual(Array.from(listeners.get(event)),[original],"event listeners not restored");
  if (mode.startsWith("uninstall")) {
    assert.equal(confirms,0,"removal attempted an installation");
    assert.deepEqual(prompts,[],"removal changed unrelated prompts");
    assert(!JSON.stringify(result).includes("fixture-secret"));
    if (mode === "uninstall-orphan") {
      assert.equal(result.ok,true,"loader absence is separate from filesystem proof");
      assert.equal(orphanFolder,true,"fixture did not model swallowed rmtree failure");
      assert.equal(JSON.parse(await eval(source)).ok,true);
      assert.equal(uninstalls,2,"unloaded orphan folder was never retried");
      assert.equal(orphanFolder,false);
      return;
    }
    if (mode === "uninstall-timeout") {
      assert.deepEqual(result,{ok:false,code:"uninstall-unconfirmed"});
      assert(window.__obsgodInstallerRunning,"pending removal lost its guard");
      assert.deepEqual(JSON.parse(await eval(source)),{ok:false,code:"busy"});
      assert.equal(uninstalls,1);
      settleConfirmation();
      await new Promise(resolve=>setImmediate(resolve));
      assert.equal(window.__obsgodInstallerRunning,undefined);
      assert.equal(JSON.parse(await eval(source)).ok,true);
      assert.equal(uninstalls,1,"already removed plugin was removed again");
      return;
    }
    assert.equal(window.__obsgodInstallerRunning,undefined);
    assert.equal(result.ok,["uninstall","uninstall-empty"].includes(mode));
    if(result.ok){assert.equal(result.removed,true);assert.deepEqual(order,["Alpha","Beta"]);}
    assert.equal(uninstalls,mode === "uninstall-empty"?0:1);
    return;
  }
  if (mode === "confirm-timeout" || mode === "confirm-timeout-reject") {
    assert.deepEqual(result,{ok:false,code:"install-unconfirmed"});
    assert.equal(confirms,1);
    assert(window.__obsgodInstallerRunning,"timed-out backend mutation lost its guard");
    const again = JSON.parse(await eval(source));
    assert.deepEqual(again,{ok:false,code:"busy"});
    assert.equal(confirms,1,"retry started another mutation while the original was pending");
    settleConfirmation(mode === "confirm-timeout-reject" ? new Error("fixture-secret late rejection") : undefined);
    await new Promise(resolve => setImmediate(resolve));
    assert.equal(window.__obsgodInstallerRunning,undefined,"settled mutation never released its guard");
    const after = JSON.parse(await eval(source));
    assert.equal(after.ok,true,"settled mutation prevented a safe retry");
    assert.equal(confirms,2);
    assert.equal(window.__obsgodInstallerRunning,undefined);
    assert.deepEqual(Array.from(listeners.get(event)),[original]);
    assert(!JSON.stringify(result).includes("fixture-secret"));
    return;
  }
  assert.equal(window.__obsgodInstallerRunning,undefined);
  if (["install","probe"].includes(mode)) assert.equal(result.ok,true);
  else assert.equal(result.ok,false);
  assert.equal(confirms,["install","reject"].includes(mode)?1:0);
  assert.deepEqual(order,["Alpha","OBSGod","Beta"]);
  assert.deepEqual(prompts,["install","reject","missing-prompt"].includes(mode)?["Other"]:[]);
  assert(!JSON.stringify(result).includes("fixture-secret"));
}).on("error", error => {throw error;});
