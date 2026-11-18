import test from "node:test";
import assert from "node:assert/strict";
import {readFileSync} from "node:fs";
import {configurationControls,configurationDraft,publicConfiguration,validConfiguration} from "../src/configuration-state.mjs";

const corpus=JSON.parse(readFileSync(new URL("../../tests/fixtures/configuration-contract.json",import.meta.url),"utf8"));
for(const entry of corpus.cases)test(`shared configuration contract: ${entry.name}`,()=>{
  assert.equal(validConfiguration(entry.input),entry.valid);
  const observed=publicConfiguration(entry.input);
  assert.equal(!!observed,entry.valid);
  for(const value of [entry.input,observed]){
    const state=configurationControls(value,100,101);
    assert.equal(state.canConfigure,entry.can_configure);
    assert.equal(state.canClose,entry.can_close);
    assert.equal(state.canChangePassword,entry.can_change_password);
  }
  if(entry.valid){
    const draft=configurationDraft(entry.input.settings);
    if(!entry.input.settings.width&&!entry.input.settings.height){
      assert.equal(draft.width,1280);assert.equal(draft.height,720);
    }
    assert.equal(draft.capture_mode,entry.input.settings.capture_mode||"screen");
    assert.equal(draft.version,1);
  }
});
