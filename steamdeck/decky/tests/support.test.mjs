import test from "node:test";
import assert from "node:assert/strict";
import {mkdtempSync,mkdirSync,writeFileSync,readFileSync,rmSync} from "node:fs";
import {tmpdir} from "node:os";
import {resolve} from "node:path";
import {parseFunding,fundingDestinations,configuredWallets,supportManifest,externalSupportUrl,openSupport,copyAddress,validAddressFormat} from "../src/support.mjs";
import {addressQr} from "../src/support-qr.mjs";
import {generateSupport} from "../../../scripts/generate-support.mjs";
import shipped from "../src/support-data.mjs";

const empty={schema_version:1,wallets:{
  bitcoin:{network:"bitcoin-mainnet",address:null},
  ethereum:{network:"ethereum-mainnet",address:null},
  solana:{network:"solana-mainnet-beta",address:null}
}};
// Public protocol examples used only as test inputs; never shipped recipients.
const eth={coin:"ethereum",network:"ethereum-mainnet",address:"0x0000000000000000000000000000000000000001"};

test("funding source yields the five explicit owner destinations without Patreon or tracking",()=>{
  const funding=parseFunding(readFileSync(new URL("../../../.github/FUNDING.yml",import.meta.url),"utf8"));
  assert.deepEqual(fundingDestinations(funding).map(x=>x.url),[
    "https://github.com/sponsors/szmyty",
    "https://www.buymeacoffee.com/szmyty",
    "https://ko-fi.com/szmyty",
    "https://opencollective.com/szmyty",
    "https://thanks.dev/u/gh/szmyty"
  ]);
  assert.deepEqual(supportManifest(funding,empty),shipped);
  assert.deepEqual(shipped.wallets,[]);
});

test("funding accepts documented scalar/list forms and fails closed on ambiguity",()=>{
  assert.deepEqual(fundingDestinations(parseFunding('---\ngithub: ["alice", bob] # note\nko_fi: \'alice\'\n')).map(x=>x.handle),["alice","bob","alice"]);
  assert.deepEqual(fundingDestinations(parseFunding("github:\n  - alice\n  - bob\n")).map(x=>x.handle),["alice","bob"]);
  assert.deepEqual(fundingDestinations(parseFunding("patreon: ''\n")),[]);
  for(const text of ["github: alice\ngithub: bob","github: [alice","github: &recipient alice","github: https://example.test/","ko_fi:\n - alice","custom: https://example.test/"]) {
    assert.throws(()=>fundingDestinations(parseFunding(text)),undefined,text);
  }
  assert.throws(()=>fundingDestinations({patreon:"szmyty"}),/Unsupported active/);
  assert.throws(()=>fundingDestinations({github:["alice","alice"]}),/Duplicate/);
});

test("external support navigation rejects altered hosts, schemes, recipients and hidden URL data",async()=>{
  const destination=fundingDestinations({github:"szmyty"})[0];
  const calls=[];
  await openSupport(destination,url=>calls.push(url));
  assert.deepEqual(calls,["https://github.com/sponsors/szmyty"]);
  for(const url of ["javascript:alert(1)","http://github.com/sponsors/szmyty","https://github.com.evil.test/sponsors/szmyty","https://github.com/sponsors/someoneelse",destination.url+"?stream_key=secret",destination.url+"#secret","https://evil@github.com/sponsors/szmyty"]) {
    assert.throws(()=>externalSupportUrl({...destination,url}));
  }
  for(const handle of ["../someoneelse","szmyty?key=secret","szmyty\n","user@example.test"])assert.throws(()=>fundingDestinations({github:handle}));
  await assert.rejects(openSupport(destination,()=>Promise.reject(new Error("offline"))),/offline/);
  await assert.rejects(openSupport(destination,undefined),/browser/);
});

test("wallets remain hidden until an explicit supported network and public address are configured",()=>{
  assert.deepEqual(configuredWallets(empty),[]);
  const configured={...empty,wallets:{...empty.wallets,ethereum:{network:eth.network,address:eth.address}}};
  assert.equal(configuredWallets(configured)[0].networkLabel,"Ethereum Mainnet");
  assert.equal(configuredWallets(configured)[0].address,eth.address);
  for(const bad of [
    {...configured,schema_version:2},
    {...configured,private_key:"never"},
    {...configured,wallets:{ethereum:{network:"arbitrum",address:eth.address}}},
    {...configured,wallets:{ethereum:{network:eth.network,address:"0xnotanaddress"}}},
    {...configured,wallets:{ethereum:{network:eth.network,address:eth.address,seed:"never"}}},
    {...configured,wallets:{dogecoin:{network:"dogecoin",address:null}}}
  ])assert.throws(()=>configuredWallets(bad));
  assert.equal(validAddressFormat("ethereum"," "+eth.address),false);
  assert.equal(validAddressFormat("bitcoin","bc1PLACEHOLDER"),false);
  assert.equal(validAddressFormat("solana","not a real address"),false);
});

test("copy sends only the receiving address and reports clipboard failure honestly",async()=>{
  const copied=[];
  await copyAddress({...eth,stream_key:"must-not-be-copied"},text=>copied.push(text));
  assert.deepEqual(copied,[eth.address]);
  await assert.rejects(copyAddress(eth,()=>Promise.reject(new Error("denied"))),/denied/);
  await assert.rejects(copyAddress({...eth,network:"wrong"},()=>{}),/Invalid/);
  await assert.rejects(copyAddress({...eth,address:""},()=>{}),/Invalid/);
});

test("receiving QR generation is deterministic, local and refuses an invalid destination",()=>{
  const first=addressQr(eth);
  assert.match(first,/^data:image\/gif;base64,R0lGOD/);
  assert.equal(first,addressQr(eth));
  assert.notEqual(first,addressQr({...eth,address:"0x0000000000000000000000000000000000000002"}));
  assert.throws(()=>addressQr({...eth,network:"wrong"}),/Invalid/);
  assert.throws(()=>addressQr({...eth,address:"placeholder"}),/Invalid/);
});

test("build generation detects stale or malformed funding instead of silently shipping old links",()=>{
  const dir=mkdtempSync(resolve(tmpdir(),"decky-stream-support-"));
  try {
    mkdirSync(resolve(dir,".github"));mkdirSync(resolve(dir,"steamdeck/decky/src"),{recursive:true});
    writeFileSync(resolve(dir,".github/FUNDING.yml"),"github: alice\n");
    writeFileSync(resolve(dir,"support.json"),JSON.stringify(empty));
    generateSupport(dir);
    const target=resolve(dir,"steamdeck/decky/src/support-data.mjs");
    const first=readFileSync(target,"utf8");
    generateSupport(dir,{check:true});generateSupport(dir);
    assert.equal(readFileSync(target,"utf8"),first);
    writeFileSync(resolve(dir,".github/FUNDING.yml"),"github: bob\n");
    assert.throws(()=>generateSupport(dir,{check:true}),/stale/);
    writeFileSync(resolve(dir,"support.json"),'{"schema_version":2,"wallets":{}}');
    assert.throws(()=>generateSupport(dir),/Unsupported/);
    assert.equal(readFileSync(target,"utf8"),first);
  } finally {rmSync(dir,{recursive:true,force:true});}
});
