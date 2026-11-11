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
      if (route === "loader/get_plugins") return [{name:"OBSGod",version:"0.1.0-test",disabled:false,load_type:1}];
      if (route === "utilities/settings/get") return [...order];
      if (route === "utilities/settings/set") {order=args[1];return;}
      if (route === "utilities/install_plugin") {
        assert.deepEqual(args,["file:///home/deck/space and %20/plugin.zip","OBSGod","0.1.0-test",digest,4]);
        for (const listener of listeners.get(event)) listener("Other","9.9.9","unrelated-request",digest,4);
        if (mode !== "missing-prompt") for (const listener of listeners.get(event)) listener("OBSGod","0.1.0-test","expected-request",digest,4);
        return;
      }
      if (route === "utilities/confirm_plugin_install") {
        assert.deepEqual(args,["expected-request"]); confirms++;
        if (mode === "reject") throw Error("fixture-secret do not expose");
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
  assert.equal(window.__obsgodInstallerRunning,undefined);
  if (["install","probe"].includes(mode)) assert.equal(result.ok,true);
  else assert.equal(result.ok,false);
  assert.equal(confirms,["install","reject"].includes(mode)?1:0);
  assert.deepEqual(order,["Alpha","OBSGod","Beta"]);
  assert.deepEqual(prompts,["install","reject","missing-prompt"].includes(mode)?["Other"]:[]);
  assert(!JSON.stringify(result).includes("fixture-secret"));
}).on("error", error => {throw error;});
