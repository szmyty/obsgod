import test from "node:test";
import assert from "node:assert/strict";
import {createView,currentResult,observe,controls} from "../src/state.mjs";

const idle={ok:true,state:"stopped",configured:true,output_known:true,recording:false,stream:{active:false,bytes:0}};
const live={...idle,state:"streaming",stream:{active:true,bytes:4096,reconnecting:false}};

test("controls use confirmed stream/operation state; unknown output keeps recovery Stop",()=>{
  assert.equal(controls(idle).stopDisabled,true);
  assert.equal(controls(idle).startDisabled,false);
  assert.equal(controls(live).stopDisabled,false);
  assert.equal(controls(live).startDisabled,true);
  const unknown={...idle,state:"unknown",output_known:false};
  assert.equal(controls(unknown).stopDisabled,false);
  assert.equal(controls(unknown).startDisabled,true);
  assert.equal(controls(idle,"start").stopLabel,"Cancel operation");
  assert.equal(controls(idle,"start").stopDisabled,false);
  assert.equal(controls(idle,"stop").stopDisabled,true);
  assert.equal(controls({...idle,operation:{action:"test-recording",state:"running"}}).stopDisabled,false);
  assert.equal(controls({...idle,recording:true}).startDisabled,true);
});

test("old polls cannot overwrite an action generation or newer backend snapshot",()=>{
  const view=createView();
  observe(view,idle,100,1,0);
  view.epoch++;
  assert.equal(observe(view,live,200,2,0).accepted,false);
  observe(view,{...live,backend_id:"first",snapshot_id:5},300,3,1);
  assert.equal(observe(view,{...idle,backend_id:"first",snapshot_id:4},400,4,1).accepted,false);
  assert.equal(view.result.stream.active,true);
  assert.equal(observe(view,{...idle,backend_id:"second",snapshot_id:1},500,5,1).accepted,true);
  assert.equal(view.result.stream.active,false);
});

test("only confirmed transitions notify, repeated replies and disconnects do not",()=>{
  const view=createView();
  assert.equal(observe(view,idle,100,1,0).transition,undefined);
  assert.equal(observe(view,live,200,2,0).transition,undefined);
  assert.equal(observe(view,{...live,stream:{...live.stream,bytes:8192}},300,3,0).transition,"streaming");
  assert.equal(observe(view,{ok:false,state:"unknown",output_known:false},400,4,0).transition,undefined);
  assert.equal(observe(view,{...live,stream:{...live.stream,bytes:8192}},500,5,0).transition,undefined);
  assert.equal(observe(view,idle,600,6,0).transition,"idle");
  assert.equal(observe(view,idle,700,7,0).transition,undefined);
});

test("stale status ages to unknown and cannot enable Start",()=>{
  const view=createView();
  observe(view,idle,100,1,0);
  assert.equal(currentResult(view,9000).state,"unknown");
  assert.equal(controls(currentResult(view,9000)).startDisabled,true);
  assert.equal(controls(currentResult(view,9000)).stopDisabled,false);
});

test("unknown replies and counter resets cannot rejuvenate a stalled stream",()=>{
  const view=createView();
  observe(view,live,100,1,0);
  assert.equal(view.progressAt,0);
  observe(view,{...live,stream:{...live.stream,bytes:8192}},200,2,0);
  assert.equal(view.progressAt,200);
  observe(view,{ok:false,state:"unknown",output_known:false},9000,3,0);
  observe(view,{...live,stream:{...live.stream,bytes:8192}},10000,4,0);
  assert.equal(view.progressAt,200);
  observe(view,{...live,stream:{...live.stream,bytes:9000}},11000,5,0);
  assert.equal(view.progressAt,11000);
  observe(view,{...live,stream:{...live.stream,bytes:50}},12000,6,0);
  assert.equal(view.progressAt,0);
  observe(view,{...live,stream:{...live.stream,bytes:100}},13000,7,0);
  assert.equal(view.progressAt,13000);
});
