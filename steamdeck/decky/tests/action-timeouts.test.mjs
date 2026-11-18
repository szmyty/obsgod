import test from "node:test";
import assert from "node:assert/strict";
import {boundedRequest,settingsTimeouts} from "../src/action-timeouts.mjs";

test("settings reply just before the UI boundary remains authoritative",async t=>{
  t.mock.timers.enable({apis:["setTimeout"]});
  let reply;
  const pending=boundedRequest(new Promise(resolve=>{reply=resolve;}),settingsTimeouts.captureMode);
  t.mock.timers.tick(settingsTimeouts.captureMode-1);
  reply({ok:true,message:"Observed saved capture"});
  assert.deepEqual(await pending,{ok:true,message:"Observed saved capture"});
  t.mock.timers.tick(1);
});

test("deadline rejects as unconfirmed and a late RPC reply cannot turn it into success",async t=>{
  t.mock.timers.enable({apis:["setTimeout"]});
  let reply,successes=0;
  const pending=boundedRequest(new Promise(resolve=>{reply=resolve;}),settingsTimeouts.captureMode,"Capture outcome unconfirmed");
  const rejected=assert.rejects(pending,/Capture outcome unconfirmed/);
  pending.then(()=>successes++,()=>{});
  t.mock.timers.tick(settingsTimeouts.captureMode);
  await rejected;
  reply({ok:true});
  await Promise.resolve();
  assert.equal(successes,0);
});

test("settings transport errors propagate while settled replies clear their deadline",async t=>{
  t.mock.timers.enable({apis:["setTimeout"]});
  const error=new Error("Unconfirmed transport");
  await assert.rejects(boundedRequest(Promise.reject(error),settingsTimeouts.configurationAction),value=>value===error);
  assert.equal(await boundedRequest(Promise.resolve("Observed settings"),settingsTimeouts.configurationRead),"Observed settings");
  t.mock.timers.tick(settingsTimeouts.configurationAction);
});
