import {health} from "./health.mjs";

export function outputKnown(result) {
  // Older preview fixtures did not expose output_known. An explicit false
  // always wins; otherwise require an actual stream snapshot from the CLI.
  return result?.output_known === true || (result?.output_known === undefined &&
    result?.ok === true && !!result?.stream && !["unknown","error","setup"].includes(result.state));
}

export function createView() {
  return {result:undefined, progressAt:0, previousBytes:undefined, lastPoll:0,
    epoch:0, latestRequest:0, lastConfirmed:undefined, backendId:undefined, snapshotId:0};
}

export function currentResult(view, now) {
  if (view.result && now-view.lastPoll>8000) return {...view.result, ok:false, state:"unknown", output_known:false};
  return view.result;
}

export function observe(view, next, now, request, epoch) {
  if (epoch !== view.epoch || request < view.latestRequest) return {accepted:false};
  if (next.backend_id === view.backendId && next.snapshot_id !== undefined && next.snapshot_id < view.snapshotId) return {accepted:false};
  const changedBackend = next.backend_id && next.backend_id !== view.backendId;
  if (changedBackend) {view.snapshotId=0;view.previousBytes=undefined;view.progressAt=0;}
  if (next.backend_id) view.backendId=next.backend_id;
  if (next.snapshot_id !== undefined) view.snapshotId=next.snapshot_id;
  const bytes=next.stream?.bytes??0;
  if (outputKnown(next)) {
    if (next.stream?.active) {
      // A nonzero counter is not evidence of current progress. Require an
      // advancing pair, preserve the baseline across unknown replies, and
      // establish a new pair after a backend/output counter reset.
      if (typeof view.previousBytes === "number" && bytes>view.previousBytes) view.progressAt=now;
      else if (typeof view.previousBytes !== "number" || bytes<view.previousBytes) view.progressAt=0;
      view.previousBytes=bytes;
    } else {view.previousBytes=undefined;view.progressAt=0;}
  }
  view.result=next;
  view.lastPoll=now;
  view.latestRequest=request;
  const state=health(next,view.progressAt,now);
  let confirmed;
  if (outputKnown(next) && !next.stream?.active) confirmed="idle";
  else if (state.live && outputKnown(next)) confirmed="streaming";
  let transition;
  if (confirmed) {
    if (view.lastConfirmed && confirmed !== view.lastConfirmed) transition=confirmed;
    view.lastConfirmed=confirmed;
  }
  return {accepted:true,transition};
}

export function controls(result, localAction="") {
  const operation=localAction || result?.operation?.action || "";
  const cancelling=operation === "stop" || result?.operation?.state === "cancelling";
  const preparing=["start","test","test-recording"].includes(operation);
  const known=outputKnown(result);
  const idle=known && !result?.stream?.active;
  return {
    startDisabled:!!operation || !result?.configured || !idle || !!result?.recording,
    testDisabled:!!operation || !result?.configured || !idle || !!result?.recording,
    stopDisabled:cancelling || (idle && !preparing),
    stopLabel:cancelling?"Stopping / cancelling…":preparing?"Cancel operation":idle?"Stop streaming":"Stop streaming / recover",
    operation,
  };
}
