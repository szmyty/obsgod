import test from "node:test";
import assert from "node:assert/strict";
import {health} from "../src/health.mjs";
test("green requires reported output and recent byte progress",()=>{
  const live={ok:true,state:"streaming",stream:{active:true,reconnecting:false,bytes:2048}};
  assert.equal(health(live,1000,1100).live,true);
  assert.equal(health(live,1000,9000).live,false);
  assert.equal(health({...live,ok:false},1000,1100).live,false);
  assert.equal(health({...live,stream:{...live.stream,reconnecting:true}},1000,1100).live,false);
  assert.equal(health({...live,stream:{...live.stream,bytes:0}},1000,1100).live,false);
});
test("unknown never looks stopped; offline and setup are distinct",()=>{
  assert.equal(health({ok:false,state:"unknown"},0,0).label,"Check OBS");
  assert.equal(health({ok:true,state:"stopped",stream:{active:false}},0,0).label,"Stopped");
  assert.equal(health({ok:true,state:"setup"},0,0).label,"Setup required");
});
