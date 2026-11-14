import test from "node:test";
import assert from "node:assert/strict";
import {createDependencyView,dependencyConsent,dependencyFreshness,dependencyObservationFailed,dependencyView,observeDependencies,readSetupLater,rememberSetupLater} from "../src/setup-state.mjs";

const obs={id:"obs",name:"OBS Studio",installed:true,compatible:true,scope:"user",version:"33.0.1"};
const gstreamer={id:"gstreamer",name:"GStreamer extension",installed:false,compatible:false,scope:null,version:null};
const missing={schema_version:1,state:"setup_required",ready:false,message:"GStreamer is missing.",reason:{code:"missing_gstreamer",message:"Install the GStreamer extension compatible with OBS."},can_install:true,can_cancel:false,dependencies:[obs,gstreamer],remote:{configured:true,needs_add:false,valid:true},operation:null};
const ready={...missing,state:"ready",ready:true,reason:null,dependencies:[obs,{...gstreamer,installed:true,compatible:true}]};

test("unknown, failed observations and expired readiness cannot enable output",()=>{
  const view=createDependencyView();
  assert.equal(dependencyView(view,100).ready,false);
  observeDependencies(view,ready,100,1,0);
  assert.equal(dependencyView(view,101).ready,true);
  assert.equal(dependencyView(view,99).ready,false);
  assert.equal(dependencyView(view,99).canInstall,false);
  assert.equal(dependencyView(view,100+dependencyFreshness+1).ready,false);
  dependencyObservationFailed(view,2,0);
  assert.equal(dependencyView(view,102).canInstall,false);
  assert.equal(dependencyView(view,102).ready,false);
  observeDependencies(view,ready,103,3,0);
  assert.equal(dependencyView(view,103).ready,true);
});

test("only the current observed ready state qualifies dependencies, never a running or failed transaction",()=>{
  for(const state of ["setup_required","running","cancelling","cancelled","interrupted","failed"]){
    const view=createDependencyView();
    observeDependencies(view,{...ready,state},100,1,0);
    assert.equal(dependencyView(view,101).ready,false,state);
  }
  const view=createDependencyView();
  assert.equal(observeDependencies(view,{...ready,schema_version:2},100,1,0),false);
  assert.equal(dependencyView(view,101).ready,false);
});

test("Late pre-action polls cannot erase a new installation or cancellation job",()=>{
  const view=createDependencyView();
  observeDependencies(view,missing,100,1,0);
  view.epoch++;
  const running={...missing,state:"running",can_cancel:true,operation:{id:"job-1",stage:"install-gstreamer"}};
  assert.equal(observeDependencies(view,running,120,3,1),true);
  assert.equal(observeDependencies(view,ready,130,2,0),false);
  assert.equal(dependencyObservationFailed(view,2,0),false);
  assert.equal(dependencyView(view,130).canCancel,true);
  assert.equal(dependencyView(view,130).canInstall,false);
  assert.equal(observeDependencies(view,{...running,state:"cancelling"},140,4,1),true);
  assert.equal(dependencyView(view,141).canCancel,false);
});

test("a surviving worker stays busy without unsafe cancellation after a backend restart",()=>{
  const view=createDependencyView();
  const running={...missing,state:"running",operation:{id:"old-worker",stage:"install-obs"}};
  for(const can_cancel of [false,undefined]){
    observeDependencies(view,{...running,can_cancel},100,1,0);
    const state=dependencyView(view,101);
    assert.equal(state.ready,false);
    assert.equal(state.busy,true);
    assert.equal(state.canInstall,false);
    assert.equal(state.canCancel,false);
  }
  observeDependencies(view,{...running,can_cancel:true},102,2,0);
  assert.equal(dependencyView(view,103).canCancel,true);
  assert.equal(dependencyView(view,101).canCancel,false);
});

test("new frontend recovers an observed backend job without scheduling an install",()=>{
  const view=createDependencyView();
  const running={...missing,state:"running",operation:{id:"persistent-job",stage:"install-obs",progress:[{level:"info",message:"Downloading OBS"}]}};
  observeDependencies(view,running,100,1,0);
  const state=dependencyView(view,101);
  assert.equal(state.busy,true);
  assert.equal(state.canInstall,false);
  assert.equal(view.status.operation.id,"persistent-job");
  assert.equal(state.ready,false);
});

test("retry consent lists only missing work after partial or cancelled installation",()=>{
  const partial={...missing,state:"cancelled",remote:{needs_add:true}};
  const lines=dependencyConsent(partial);
  assert.equal(lines.length,2);
  assert.match(lines[0],/Flathub/);
  assert.match(lines[1],/GStreamer/);
  assert.equal(lines.some(line=>line.startsWith("OBS Studio")),false);
  const view=createDependencyView();
  observeDependencies(view,partial,100,1,0);
  assert.equal(dependencyView(view,101).canInstall,true);
  assert.equal(dependencyView(view,101,"install").canInstall,false);
  observeDependencies(view,{...partial,can_install:false,reason:{code:"scope",message:"OBS is installed system-wide; use the supported scope."}},102,2,0);
  assert.equal(dependencyView(view,103).canInstall,false);
  assert.match(dependencyView(view,103).reason,/system-wide/);
});

test("Later persists only a postponement preference and never changes observed readiness",()=>{
  const entries=new Map();
  const storage={getItem:key=>entries.get(key),setItem:(key,value)=>entries.set(key,value),removeItem:key=>entries.delete(key)};
  const view=createDependencyView();
  observeDependencies(view,missing,100,1,0);
  rememberSetupLater(storage,true);
  assert.equal(readSetupLater(storage),true);
  assert.equal(dependencyView(view,101).ready,false);
  assert.equal(dependencyView(view,101).canInstall,true);
  assert.deepEqual([...entries.values()],["1"]);
  rememberSetupLater(storage,false);
  assert.equal(readSetupLater(storage),false);
  const blocked={getItem(){throw Error("denied");},setItem(){throw Error("denied");},removeItem(){throw Error("denied");}};
  assert.equal(readSetupLater(blocked),false);
  assert.doesNotThrow(()=>rememberSetupLater(blocked,true));
});
