import test from "node:test";
import assert from "node:assert/strict";
import {createTalkLease} from "../src/mixer-talk.mjs";
const settle=async()=>{for(let i=0;i<8;i++)await Promise.resolve();};

test("releasing while talk acquisition is pending releases its late token",async()=>{
  const calls=[];let finish;const states=[];
  const lease=createTalkLease(payload=>{calls.push(payload);return payload.action==="talk-start"?new Promise(resolve=>{finish=resolve;}):Promise.resolve({ok:true});},value=>states.push(value));
  lease.press();lease.press();lease.release();
  finish({ok:true,talk_token:"late",lease_ms:1200});await settle();
  assert.equal(calls.filter(call=>call.action==="talk-start").length,1);
  assert.deepEqual(calls.at(-1),{action:"talk-release",token:"late"});
  assert.ok(!states.includes(true));lease.dispose();
});
test("only an explicit press renews a lease; release prevents renewal",async t=>{
  t.mock.timers.enable({apis:["setTimeout"]});const calls=[];const states=[];
  const lease=createTalkLease(async payload=>{calls.push(payload);return {ok:true,talk_token:"held",lease_ms:1200};},value=>states.push(value));
  lease.press();await settle();t.mock.timers.tick(400);await settle();
  assert.deepEqual(calls[1],{action:"talk-start",token:"held"});
  lease.release();await settle();t.mock.timers.tick(5000);await settle();
  assert.equal(calls.filter(call=>call.action==="talk-start").length,2);
  assert.equal(states.at(-1),false);lease.dispose();
});
test("a hung renewal expires the UI lease and releases the token",async t=>{
  t.mock.timers.enable({apis:["setTimeout"]});const calls=[];const failures=[];const states=[];
  const lease=createTalkLease(payload=>{calls.push(payload);if(payload.action==="talk-start"&&calls.length>1)return new Promise(()=>{});return Promise.resolve({ok:true,talk_token:"held",lease_ms:1200});},value=>states.push(value),message=>failures.push(message));
  lease.press();await settle();t.mock.timers.tick(400);await settle();t.mock.timers.tick(700);await settle();
  assert.equal(states.at(-1),false);assert.equal(failures.length,1);
  assert.ok(calls.some(call=>call.action==="talk-release"&&call.token==="held"));lease.dispose();
});
test("dispose and focus cancellation request fail-closed cancellation",async()=>{
  const calls=[];const lease=createTalkLease(async payload=>{calls.push(payload);return {ok:true,talk_token:"held"};});
  lease.cancel();lease.dispose();lease.press();await settle();
  assert.equal(calls.filter(call=>call.action==="talk-cancel").length,2);
  assert.equal(calls.filter(call=>call.action==="talk-start").length,0);
});
test("an already expired backend lease never displays talking",async()=>{
  const calls=[],states=[],failures=[];
  const lease=createTalkLease(async payload=>{calls.push(payload);return {ok:true,talk_token:"expired",lease_ms:1200,talk_expires_at:"2000-01-01T00:00:00Z"};},state=>states.push(state),message=>failures.push(message));
  lease.press();await settle();
  assert.ok(!states.includes(true));assert.equal(failures.length,1);
  assert.ok(calls.some(call=>call.action==="talk-release"&&call.token==="expired"));lease.dispose();
});
