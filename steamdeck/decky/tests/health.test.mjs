import test from "node:test";
import assert from "node:assert/strict";
import {health} from "../src/health.mjs";
test("green requires reported output and recent byte progress",()=>{
  const live={ok:true,state:"streaming",output_known:true,stream:{active:true,reconnecting:false,bytes:2048}};
  assert.equal(health(live,1000,1100).live,true);
  assert.equal(health(live,1000,9000).live,false);
  assert.equal(health({...live,ok:false},1000,1100).live,false);
  assert.equal(health({...live,stream:{...live.stream,reconnecting:true}},1000,1100).live,false);
  assert.equal(health({...live,stream:{...live.stream,bytes:0}},1000,1100).live,false);
});
test("unknown never looks stopped; offline and setup are distinct",()=>{
  assert.equal(health({ok:false,state:"unknown"},0,0).label,"Check OBS");
  assert.equal(health({ok:true,state:"stopped",output_known:true,stream:{active:false}},0,0).label,"Stopped");
  assert.equal(health({ok:true,state:"setup"},0,0).label,"Setup required");
});
test("unconfirmed or blank capture cannot show healthy green",()=>{
  const live={ok:true,state:"streaming",output_known:true,stream:{active:true,bytes:4096}};
  assert.equal(health({...live,output_known:false},1000,1100).live,false);
  assert.equal(health({...live,frames:"blank"},1000,1100).label,"Check capture");
  assert.equal(health({...live,frames:"unknown"},1000,1100).live,false);
  assert.equal(health({...live,frames:"visible"},1000,1100).live,true);
  assert.equal(health({...live,frames:"visible",capture:"unavailable"},1000,1100).live,false);
  assert.equal(health({ok:true,state:"stopped",output_known:true,recording:true},0,0).label,"Recording locally");
});

test("missing or mistyped output knowledge cannot display a healthy stream from old byte progress",()=>{
  for(const output_known of [undefined,null,"true",1]){
    const state=health({ok:true,state:"streaming",output_known,frames:"visible",stream:{active:true,bytes:4096}},1000,1100);
    assert.equal(state.live,false);assert.equal(state.label,"Check OBS");
  }
});

test("intentional between-game screen requires matching mode, scene and advancing output",()=>{
  const idle={ok:true,state:"streaming",output_known:true,stream:{active:true,bytes:4096},settings:{capture_mode:"game"},runtime:{scene:"OBSGod Idle"},game:"idle",frames:"placeholder",capture:"unavailable"};
  assert.equal(health(idle,1000,1100).label,"Streaming · between games");
  assert.equal(health(idle,1000,9000).live,false);
  assert.equal(health({...idle,settings:{capture_mode:"screen"}},1000,1100).live,false);
  assert.equal(health({...idle,runtime:{scene:"OBSGod Live"}},1000,1100).live,false);
  assert.equal(health({...idle,output_known:false},1000,1100).live,false);
});
