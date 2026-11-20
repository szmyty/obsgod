import test from 'node:test';
import assert from 'node:assert/strict';
import {clipListResult, mediaControls, healthFresh, metricText, profileSummary} from '../src/advanced-state.mjs';

const idle={configured:true,output_known:true,process:'running',stream:{active:false},media:{known:true,recording:{active:false},replay_active:false}};
test('portable profile microphone summaries describe an initial default, never current mute state',()=>{
  const profile={width:1280,height:720,fps:30,bitrate:4500,encoder:'vaapi',capture_mode:'screen',microphone:false};
  assert.match(profileSummary(profile),/initial microphone default off/);
  assert.match(profileSummary({...profile,microphone:true}),/initial microphone default on/);
  assert.doesNotMatch(profileSummary(profile),/microphone (?:muted|disabled|live)/);
});
test('replay and unknown output cannot authorize profile edits or another output',()=>{
  assert.equal(mediaControls(idle).idle,true);
  assert.equal(mediaControls({...idle,media:{...idle.media,replay_active:true}}).idle,false);
  assert.equal(mediaControls({...idle,media:{known:false}}).recordStartDisabled,true);
  assert.equal(mediaControls({...idle,output_known:false}).replaySaveDisabled,true);
  assert.equal(mediaControls({...idle,media:undefined}).idle,false);
  assert.equal(mediaControls({...idle,media:undefined,process:'absent'}).idle,true);
});
test('Stop/recover remains possible for unknown recording/replay state',()=>{
  const state=mediaControls({...idle,output_known:false,media:{known:false}});
  assert.equal(state.recordStopDisabled,false);assert.equal(state.replayStopDisabled,false);
  assert.equal(mediaControls({...idle,media:{...idle.media,replay_active:true}}).replaySaveDisabled,false);
  assert.equal(mediaControls(idle,true).recordStopDisabled,true);
});
test('metrics become unknown on expiry, malformed values and future timestamps',()=>{
  const now=Date.parse('2026-11-13T12:00:00Z');
  const report={observed_at:'2026-11-13T11:59:59Z',expires_at:'2026-11-13T12:00:07Z',metrics:{bitrate_kbps:4500,cpu_percent:0}};
  assert.equal(healthFresh(report,now),true);
  assert.equal(metricText(report,'bitrate_kbps',' kbps',now,0),'4500 kbps');
  assert.equal(metricText(report,'cpu_percent','%',now),'0.0%');
  assert.equal(metricText(report,'gpu_percent','%',now),'Not measured');
  assert.equal(metricText(report,'bitrate_kbps',' kbps',now+8000),'Not measured');
  assert.equal(healthFresh({...report,observed_at:'2026-11-13T12:01:00Z'},now),false);
  assert.equal(metricText({...report,metrics:{cpu_percent:NaN}},'cpu_percent','%',now),'Not measured');
});

test('only a successful completed clip list can establish an empty library',()=>{
  assert.deepEqual(clipListResult({ok:true,clips:[]}),{state:'empty',clips:[]});
  for(const reply of [undefined,{}, {ok:false,clips:[]},{ok:true},{ok:true,clips:null},{ok:true,clips:{length:0}}]){
    assert.deepEqual(clipListResult(reply),{state:'error',clips:[]});
  }
});
test('clip list selects display fields and rejects malformed rows instead of inventing an empty result',()=>{
  const clip={name:'my game.mkv',kind:'recording',bytes:1048576,modified_utc:'2026-11-13T12:00:00Z'};
  assert.deepEqual(clipListResult({ok:true,clips:[{...clip,private_token:'MUST-NOT-COPY'}]}),{state:'ready',clips:[clip]});
  for(const change of [{bytes:-1},{bytes:NaN},{bytes:1.5},{bytes:Number.MAX_SAFE_INTEGER+1},{modified_utc:'invalid'},{name:'bad\nname'},{kind:''}]){
    assert.deepEqual(clipListResult({ok:true,clips:[{...clip,...change}]}),{state:'error',clips:[]});
  }
});
