// Pure public-support configuration. Nothing here reads stream settings,
// credentials, telemetry, a network service, or a private cryptocurrency key.
export const providerDefinitions = Object.freeze({
  github: {label:"GitHub Sponsors", symbol:"♥", base:"https://github.com/sponsors/"},
  buy_me_a_coffee: {label:"Buy Me a Coffee", symbol:"☕", base:"https://www.buymeacoffee.com/"},
  ko_fi: {label:"Ko-fi", symbol:"♡", base:"https://ko-fi.com/"},
  open_collective: {label:"Open Collective", symbol:"◎", base:"https://opencollective.com/"},
  thanks_dev: {label:"thanks.dev", symbol:"✦", base:"https://thanks.dev/"}
});

export const walletDefinitions = Object.freeze({
  bitcoin: {label:"Bitcoin", symbol:"₿", network:"bitcoin-mainnet", networkLabel:"Bitcoin Mainnet"},
  ethereum: {label:"Ethereum", symbol:"◆", network:"ethereum-mainnet", networkLabel:"Ethereum Mainnet"},
  solana: {label:"Solana", symbol:"≋", network:"solana-mainnet-beta", networkLabel:"Solana Mainnet Beta"}
});

function plainObject(value) {
  return value !== null && typeof value === "object" && !Array.isArray(value) &&
    (Object.getPrototypeOf(value) === Object.prototype || Object.getPrototypeOf(value) === null);
}

function scalar(value) {
  const text=value.trim();
  if (!text || text==="null" || text==="~" || text==='""' || text==="''") return "";
  if (/^"[^"\\]*"$/.test(text) || /^'[^']*'$/.test(text)) return text.slice(1,-1);
  if (/^[A-Za-z0-9_./-]+$/.test(text)) return text;
  throw new Error("Funding handles must be plain strings without YAML expressions or URLs.");
}

/** The repository's intentionally small FUNDING subset: scalar handles or a
 * GitHub scalar/list. Unsupported active providers and syntax fail the build
 * instead of silently changing a recipient. This is not a general YAML parser.
 */
export function parseFunding(text) {
  if(typeof text!=="string" || text.length>16384)throw new Error("Invalid funding configuration.");
  const result=Object.create(null);
  let listKey="";
  for(const raw of text.split(/\r?\n/)) {
    const line=raw.replace(/\s+#.*$/,"").trimEnd();
    if(!line.trim() || line.trimStart().startsWith("#") || line==="---")continue;
    const item=line.match(/^\s+-\s+(.+)$/);
    if(item) {
      if(listKey!=="github")throw new Error("Only github supports a list of funding handles.");
      result.github.push(scalar(item[1]));
      continue;
    }
    const match=line.match(/^([a-z_]+):\s*(.*)$/);
    if(!match)throw new Error("Unsupported FUNDING.yml syntax; use a flat provider-to-handle mapping.");
    const [,key,input]=match;
    if(Object.hasOwn(result,key))throw new Error("Duplicate funding provider: "+key);
    listKey="";
    if(key==="github" && (!input || input.startsWith("["))) {
      if(input && !input.endsWith("]"))throw new Error("Invalid github funding list.");
      result[key]=input ? input.slice(1,-1).split(",").filter(v=>v.trim()).map(scalar) : [];
      if(!input)listKey=key;
    } else result[key]=scalar(input);
  }
  return result;
}

function validHandle(key,handle) {
  if(typeof handle!=="string")return false;
  if(key==="thanks_dev")return /^u\/gh\/[A-Za-z0-9][A-Za-z0-9-]{0,38}$/.test(handle);
  return /^[A-Za-z0-9][A-Za-z0-9_-]{0,79}$/.test(handle);
}

export function fundingDestinations(funding) {
  if(!plainObject(funding))throw new Error("Invalid funding providers.");
  for(const [key,value] of Object.entries(funding)) {
    const active=Array.isArray(value) ? value.some(Boolean) : Boolean(value);
    if(active && !Object.hasOwn(providerDefinitions,key))throw new Error("Unsupported active funding provider: "+key);
    if(Array.isArray(value) && key!=="github")throw new Error("Only github supports multiple handles.");
  }
  const result=[];
  for(const [key,definition] of Object.entries(providerDefinitions)) {
    const configured=funding[key];
    const handles=Array.isArray(configured) ? configured : [configured];
    for(const handle of handles.filter(Boolean)) {
      if(!validHandle(key,handle))throw new Error("Invalid funding handle for "+key);
      if(result.some(entry=>entry.id===key+":"+handle))throw new Error("Duplicate funding destination.");
      result.push({id:key+":"+handle,provider:key,label:definition.label,symbol:definition.symbol,
        handle,url:definition.base+handle});
    }
  }
  return result;
}

// Deliberate format checks, not checksum, ownership, balance or payout checks.
// The owner must verify every address with its wallet before enabling it.
export function validAddressFormat(coin,address) {
  if(typeof address!=="string" || address!==address.trim())return false;
  if(coin==="bitcoin")return /^(?:bc1[ac-hj-np-z02-9]{11,71}|[13][1-9A-HJ-NP-Za-km-z]{25,34})$/.test(address);
  if(coin==="ethereum")return /^0x[0-9a-fA-F]{40}$/.test(address);
  if(coin==="solana")return /^[1-9A-HJ-NP-Za-km-z]{32,44}$/.test(address);
  return false;
}

export function configuredWallets(config) {
  if(!plainObject(config) || config.schema_version!==1 ||
    Object.keys(config).some(key=>!["schema_version","wallets"].includes(key)) || !plainObject(config.wallets)) {
    throw new Error("Unsupported support configuration; expected schema_version 1 and wallets.");
  }
  const wallets=[];
  for(const [coin,entry] of Object.entries(config.wallets)) {
    if(!Object.hasOwn(walletDefinitions,coin) || !plainObject(entry) ||
      Object.keys(entry).some(key=>!["network","address"].includes(key)))throw new Error("Invalid cryptocurrency configuration.");
    const definition=walletDefinitions[coin];
    if(entry.network!==definition.network)throw new Error("Unsupported network for "+coin);
    if(entry.address===null || entry.address==="")continue;
    if(!validAddressFormat(coin,entry.address))throw new Error("Invalid public address format for "+coin);
    wallets.push({coin,label:definition.label,symbol:definition.symbol,network:definition.network,
      networkLabel:definition.networkLabel,address:entry.address});
  }
  return wallets;
}

export function supportManifest(funding,config) {
  return {schema_version:1,providers:fundingDestinations(funding),wallets:configuredWallets(config)};
}

export function externalSupportUrl(destination) {
  if(!plainObject(destination) || !Object.hasOwn(providerDefinitions,destination.provider) ||
    !validHandle(destination.provider,destination.handle))throw new Error("Invalid support destination.");
  const expected=providerDefinitions[destination.provider].base+destination.handle;
  if(destination.url!==expected)throw new Error("Support destination does not match its configured provider.");
  return expected;
}

export async function openSupport(destination,navigate) {
  const url=externalSupportUrl(destination);
  if(typeof navigate!=="function")throw new Error("External browser unavailable.");
  await navigate(url);
}

export async function copyAddress(wallet,writeText) {
  const definition=walletDefinitions[wallet?.coin];
  if(!definition || wallet.network!==definition.network || !validAddressFormat(wallet.coin,wallet.address)) {
    throw new Error("Invalid receiving address.");
  }
  if(typeof writeText!=="function")throw new Error("Clipboard unavailable.");
  await writeText(wallet.address);
}
