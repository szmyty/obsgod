import test from "node:test";
import assert from "node:assert/strict";
import {createHash} from "node:crypto";
import {readFileSync} from "node:fs";
import {auroraIcon,auroraSourceSHA256} from "../src/aurora-brand.mjs";

test("selected decorative mark is local, fontless, source-bound vector data",()=>{
  assert.ok(auroraIcon.startsWith("data:image/svg+xml,"));
  const svg=decodeURIComponent(auroraIcon.slice("data:image/svg+xml,".length));
  const original=readFileSync(new URL("../../../.identity/candidates/aurora/mark-small.svg",import.meta.url),"utf8");
  assert.equal(svg,original);
  assert.equal(createHash("sha256").update(svg).digest("hex"),auroraSourceSHA256);
  assert.match(svg,/<linearGradient/);
  assert.doesNotMatch(svg,/<(?:script|image|text|foreignObject)\b|(?:href|onload)\s*=/i);
  for(const ref of svg.matchAll(/url\(([^)]+)\)/g))assert.match(ref[1],/^#[A-Za-z][A-Za-z0-9_-]*$/);
});
