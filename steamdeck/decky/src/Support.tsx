import {ButtonItem,ConfirmModal,Navigation,PanelSection,PanelSectionRow,showModal} from "@decky/ui";
import {useMemo,useState} from "react";
import metadata from "./support-data.mjs";
import {copyAddress,openSupport,walletDefinitions} from "./support.mjs";
import {addressQr} from "./support-qr.mjs";

type Destination={id:string;provider:string;label:string;symbol:string;handle:string;url:string};
type Wallet={coin:string;label:string;symbol:string;network:string;networkLabel:string;address:string};

async function writeClipboard(text:string) {
  try {
    if(navigator.clipboard?.writeText) {await navigator.clipboard.writeText(text);return;}
  } catch {/* Steam may deny the asynchronous clipboard API. */}
  const focused=document.activeElement;
  const field=document.createElement("textarea");
  field.value=text;field.readOnly=true;field.setAttribute("aria-hidden","true");
  field.style.cssText="position:fixed;left:0;top:0;width:1px;height:1px;opacity:0";
  document.body.appendChild(field);
  try {
    field.select();
    if(!document.execCommand("copy"))throw new Error("Clipboard unavailable.");
  } finally {
    field.remove();
    if(focused instanceof HTMLElement)focused.focus({preventScroll:true});
  }
}

export function ReceiveAddress({wallet}:{wallet:Wallet}) {
  const [notice,setNotice]=useState("");
  const [copying,setCopying]=useState(false);
  const qr=useMemo(()=>{try{return addressQr(wallet);}catch{return "";}},[wallet.coin,wallet.address,wallet.network]);
  async function copy() {
    if(copying)return;
    setCopying(true);setNotice("");
    try {await copyAddress(wallet,writeClipboard);setNotice("Address copied. Verify the network and address in your wallet before sending.");}
    catch {setNotice("Clipboard unavailable. Scan the QR code or select the full address below.");}
    finally {setCopying(false);}
  }
  return <div style={{display:"grid",gap:12,fontSize:15,lineHeight:1.5}}>
    <div><strong>{wallet.networkLabel}</strong><br/>Send only {wallet.label} on this network. Verify the destination in your wallet before sending.</div>
    {qr?<img src={qr} alt={`${wallet.label} public receiving address QR code`} width={220} height={220} style={{background:"white",padding:4,maxWidth:"100%",imageRendering:"pixelated"}}/>:<div>QR unavailable. Use the address below.</div>}
    <div aria-label={`${wallet.label} receiving address`} style={{fontFamily:"monospace",overflowWrap:"anywhere",userSelect:"text",fontSize:14}}>{wallet.address}</div>
    <ButtonItem layout="below" onClick={()=>void copy()}>{copying?"Copying…":"Copy address"}</ButtonItem>
    <div role="status" aria-live="polite">{notice}</div>
  </div>;
}

function showReceivingAddress(wallet:Wallet) {
  let modal:ReturnType<typeof showModal>;
  const close=()=>modal?.Close();
  modal=showModal(<ConfirmModal strTitle={`Support with ${wallet.label}`}
    strDescription={<ReceiveAddress wallet={wallet}/>} strOKButtonText="Done" strCancelButtonText="Close"
    onOK={close} onCancel={close} closeModal={close}/>);
}

export function Support({preview=false}:{preview?:boolean}) {
  const [notice,setNotice]=useState("");
  const providers=metadata.providers as Destination[];
  const wallets=metadata.wallets as Wallet[];
  async function open(destination:Destination) {
    setNotice("");
    try {await openSupport(destination,(url:string)=>Navigation.NavigateToExternalWeb(url));}
    catch {setNotice(`Could not open ${destination.label}. Try again when the browser and connection are available.`);}
  }
  if(!providers.length && !wallets.length && !preview)return null;
  return <PanelSection title="SUPPORT DEVELOPMENT">
    <PanelSectionRow><div style={{fontSize:13,lineHeight:1.5,opacity:.85}}>Enjoy streaming? Support ongoing development. Contributions are optional.</div></PanelSectionRow>
    {providers.map(destination=><PanelSectionRow key={destination.id}>
      <ButtonItem layout="below" icon={<span aria-hidden="true" style={{fontSize:22}}>{destination.symbol}</span>}
        description="Opens an external support page" onClick={()=>void open(destination)}>{destination.label}</ButtonItem>
    </PanelSectionRow>)}
    {wallets.map(wallet=><PanelSectionRow key={wallet.coin}>
      <ButtonItem layout="below" icon={<span aria-hidden="true" style={{fontSize:22}}>{wallet.symbol}</span>}
        description={wallet.networkLabel} onClick={()=>showReceivingAddress(wallet)}>Support with {wallet.label}</ButtonItem>
    </PanelSectionRow>)}
    {preview&&Object.entries(walletDefinitions).filter(([coin])=>!wallets.some(wallet=>wallet.coin===coin)).map(([coin,definition])=><PanelSectionRow key={coin}>
      <ButtonItem layout="below" disabled icon={<span aria-hidden="true">{definition.symbol}</span>}
        description="Design preview · receiving address not configured">Support with {definition.label}</ButtonItem>
    </PanelSectionRow>)}
    {notice&&<PanelSectionRow><div role="status" aria-live="polite" style={{fontSize:13,lineHeight:1.5}}>{notice}</div></PanelSectionRow>}
  </PanelSection>;
}

export default Support;
