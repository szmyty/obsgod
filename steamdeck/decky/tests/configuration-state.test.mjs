import test from "node:test";
import assert from "node:assert/strict";
import {configurationControls,configurationDraft,configurationPayload,destinationChanged,inferredProvider,providers,validateControlPassword,validateDestination} from "../src/configuration-state.mjs";

const server="rtmps://example.invalid/app";
const saved={schema_version:1,ok:true,configured:true,provider:"custom",settings:{server,bitrate:6000,fps:60,encoder:"vaapi",width:1920,height:1080,capture_mode:"game",microphone:true,idle_style:"video",idle_media:"/private/idle.webm",idle_media_rights:"Owner rights",idle_text:"Saved message"},output_known:true,can_configure:true,connection:{process:"absent",output_known:true}};

test("blank keys retain only the same saved provider/server binding, including an explicit account-key replacement",()=>{
  const draft=configurationDraft(saved.settings);
  assert.equal(validateDestination(saved,"custom",draft,""),"");
  assert.equal(destinationChanged(saved,"custom",server),false);
  assert.match(validateDestination(saved,"kick",draft,""),/key for this destination/);
  assert.match(validateDestination(saved,"custom",{...draft,server:"rtmps://other.invalid/app"},""),/key for this destination/);
  assert.equal(validateDestination(saved,"custom",{...draft,server:"rtmps://other.invalid/app"},"new-account-key"),"");
  assert.match(validateDestination({...saved,configured:false},"custom",draft,""),/key for this destination/);
  assert.match(validateDestination(saved,"custom",draft,"",true),/key for this destination/);
});

test("URL validation rejects embedded credentials and query/fragment without guessing secrets from URL paths",()=>{
  const draft=configurationDraft(saved.settings);
  for(const value of ["https://example.invalid/app","rtmps://user:password@example.invalid/app","rtmps://example.invalid/app?key=sentinel","rtmps://example.invalid/app#key","rtmps://"]){
    const result=validateDestination(saved,"custom",{...draft,server:value},"synthetic-key");
    assert.match(result,/RTMP\(S\) server URL/);
    assert.equal(result.includes("sentinel"),false);
  }
  assert.equal(validateDestination(saved,"custom",{...draft,server:"rtmp://localhost/app/arbitrary-path"},"synthetic-key"),"");
});

test("private readback fields never enter a draft or settings patch; untouched advanced state remains backend-owned",()=>{
  const poisoned={...saved.settings,stream_key:"KEY-SENTINEL",obs_password:"PASSWORD-SENTINEL",setup_token:"TOKEN-SENTINEL"};
  const draft=configurationDraft(poisoned);
  assert.equal(JSON.stringify(draft).includes("SENTINEL"),false);
  const payload=configurationPayload(saved,"custom",draft,"",{});
  assert.deepEqual(payload,{});
  assert.equal("idle_media" in payload,false);
  assert.equal("width" in payload,false);
  assert.deepEqual(configurationPayload(saved,"custom",{...draft,bitrate:4500},"",{bitrate:true}),{bitrate:4500});
  assert.deepEqual(configurationPayload(saved,"kick",draft,"replacement-key",{}),{stream_key:"replacement-key",replace_key:true});
  assert.deepEqual(configurationPayload(saved,"custom",draft,"replacement-key",{},true),{stream_key:"replacement-key",replace_key:true});
  const first=configurationPayload({...saved,configured:false},"custom",configurationDraft(),"new-key",{});
  assert.equal(first.bitrate,4500);
  assert.equal(first.fps,30);
  assert.equal(first.capture_mode,"screen");
});

test("active/unknown/stale/backward-clock/dependency-busy observations cannot authorize changes",()=>{
  assert.equal(configurationControls(saved,100,101).canConfigure,true);
  assert.equal(configurationControls(saved,100,101).canChangePassword,true);
  for(const [status,now,options] of [
    [{...saved,can_configure:false},101,{}],
    [{...saved,output_known:false},101,{}],
    [saved,20101,{}],
    [saved,99,{}],
    [saved,101,{busy:true}]
  ]){
    const controls=configurationControls(status,100,now,options);
    assert.equal(controls.canConfigure,false);
    assert.equal(controls.canChangePassword,false);
  }
  assert.equal(configurationControls({...saved,connection:{process:"running",output_known:true}},100,101).canChangePassword,false);
  const idleOpen={...saved,can_configure:false,can_close:true,connection:{process:"running",output_known:true}};
  assert.equal(configurationControls(idleOpen,100,101).canClose,true);
  assert.equal(configurationControls({...idleOpen,output_known:false},100,101).canClose,false);
  assert.equal(configurationControls(idleOpen,100,101,{busy:true}).canClose,false);
  assert.equal(configurationControls(idleOpen,100,99).canClose,false);
});

test("provider guides preserve established endpoint classification and never invent a Kick account URL",()=>{
  assert.equal(providers.kick.preset,undefined);
  assert.equal(inferredProvider(providers.twitch.preset),"twitch");
  assert.equal(inferredProvider("rtmps://a.rtmps.youtube.com/live2"),"youtube");
  assert.equal(inferredProvider("rtmps://account.global-contribute.live-video.net/app"),"kick");
  assert.equal(inferredProvider("rtmp://localhost/app"),"custom");
});

test("quality and control-password boundaries reject malformed values without echoing secrets",()=>{
  const draft=configurationDraft(saved.settings);
  for(const patch of [{bitrate:999},{fps:24},{encoder:"unknown"},{width:10,height:10},{capture_mode:"fallback"}])assert.notEqual(validateDestination(saved,"custom",{...draft,...patch},""),"");
  for(const secret of ["short","a".repeat(129),"password\nSENTINEL"])assert.match(validateControlPassword(secret),/12–128 bytes/);
  assert.equal(validateControlPassword("long-local-password"),"");
  assert.equal(validateControlPassword("😀".repeat(33)).includes("12–128 bytes"),true);
});
