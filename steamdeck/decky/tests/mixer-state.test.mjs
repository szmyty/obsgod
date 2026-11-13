import test from 'node:test';
import assert from 'node:assert/strict';
import {mixerFresh,mixerView,mixerNotice,mixerGain} from '../src/mixer-state.mjs';

const now=Date.parse('2026-11-13T12:00:00Z');
function sample(){return {known:true,observed_at:'2026-11-13T11:59:59Z',expires_at:'2026-11-13T12:00:07Z',preferences:{microphone_enabled:true,microphone_muted:true,push_to_talk:false},microphone:{known:true,available:true,muted:true,system_muted:false,peak_dbfs:-12}};}

test('unknown, stale and future observations never authorize microphone unmute',()=>{
  for(const mixer of [undefined,{...sample(),known:false},{...sample(),expires_at:'2026-11-13T12:00:00Z'},{...sample(),observed_at:'2026-11-13T12:00:02Z'},{...sample(),expires_at:'2026-11-13T12:05:00Z'}]){
    const state=mixerView(mixer,false,now);
    assert.equal(state.unmuteDisabled,true);
    assert.equal(state.talkDisabled,true);
    assert.equal(state.actualMuted,undefined);
    assert.equal(state.level,undefined);
  }
  assert.equal(mixerFresh(sample(),now),true);
});

test('a disconnected or system-muted microphone stays visibly separate from saved preferences',()=>{
  const lost={...sample(),microphone:{known:true,available:false,muted:true}};
  assert.equal(mixerView(lost,false,now).unmuteDisabled,true);
  assert.match(mixerView(lost,false,now).label,/unavailable/);
  const system={...sample(),microphone:{known:true,available:true,muted:false,system_muted:true,peak_dbfs:-6}};
  assert.equal(mixerView(system,false,now).unmuteDisabled,true);
  assert.match(mixerView(system,false,now).label,/SteamOS/);
  assert.equal(mixerView(system,false,now).level,undefined);
  const muted=mixerView(sample(),false,now);
  assert.equal(muted.unmuteDisabled,false);
  assert.match(muted.label,/muted on stream/);
  assert.equal(muted.level,undefined);
  const live=mixerView({...sample(),microphone:{...sample().microphone,muted:false}},false,now);
  assert.equal(live.level,-12);
  const unknownInput=mixerView({...sample(),microphone:{...sample().microphone,known:false}},false,now);
  assert.equal(unknownInput.unmuteDisabled,true);
  assert.equal(unknownInput.actualMuted,undefined);
});

test('hold-to-talk requires current available input and explicit unmuted permission',()=>{
  const mixer={...sample(),preferences:{microphone_enabled:true,microphone_muted:false,push_to_talk:true}};
  assert.equal(mixerView(mixer,false,now).talkDisabled,false);
  assert.equal(mixerView(mixer,false,now).unmuteDisabled,true);
  assert.equal(mixerView(mixer,true,now).talkDisabled,true);
  assert.equal(mixerView({...mixer,preferences:{...mixer.preferences,microphone_muted:true}},false,now).talkDisabled,true);
});

test('device-change notices fire once per observed transition, not once per poll',()=>{
  const seen=new Set();
  const mixer={notice:{code:'microphone-unavailable',revision:'route-1',message:'The selected microphone disappeared; stream microphone kept muted.'}};
  assert.equal(mixerNotice(mixer,seen)?.code,'microphone-unavailable');
  assert.equal(mixerNotice(mixer,seen),undefined);
  assert.equal(mixerNotice({...mixer,notice:{...mixer.notice,revision:'route-2'}},seen)?.code,'microphone-unavailable');
  assert.equal(mixerNotice({notice:{code:'unknown',message:'No transition identity'}},seen),undefined);
});

test('gain limits retain zero and reject malformed preferences',()=>{
  assert.equal(mixerGain(0),0);assert.equal(mixerGain(200),200);assert.equal(mixerGain(1.5),1.5);
  for(const value of [NaN,Infinity,-1,201,'100',null])assert.equal(mixerGain(value),100);
});
