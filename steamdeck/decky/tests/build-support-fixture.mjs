// Development browser fixture only. Public protocol examples below are test
// inputs, never product support recipients; production support.json stays empty.
import {build} from "esbuild";

await build({
  stdin:{contents:`
    import React from "react";
    import {createRoot} from "react-dom/client";
    import {Support} from "./src/Support";
    import metadata from "./src/support-data.mjs";
    import {configuredWallets} from "./src/support.mjs";
    const examples={schema_version:1,wallets:{
      bitcoin:{network:"bitcoin-mainnet",address:"1BoatSLRHtKNngkdXEeobR76b53LETtpyT"},
      ethereum:{network:"ethereum-mainnet",address:"0x0000000000000000000000000000000000000001"},
      solana:{network:"solana-mainnet-beta",address:"11111111111111111111111111111111"}
    }};
    metadata.wallets=configuredWallets(examples);
    window.supportFixture={examples,externalLinks:[]};
    createRoot(document.getElementById("root")).render(React.createElement(Support));
  `,resolveDir:process.cwd()},
  outfile:process.argv[2],bundle:true,format:"iife",platform:"browser",minify:false,
  plugins:[{
    name:"simulated-decky-ui",
    setup(build){
      build.onResolve({filter:/^@decky\/ui$/},()=>({path:"simulated-ui",namespace:"fixture"}));
      build.onLoad({filter:/.*/,namespace:"fixture"},()=>({loader:"js",resolveDir:process.cwd(),contents:`
        import React from "react";
        import {createRoot} from "react-dom/client";
        export const PanelSection=({title,children})=>React.createElement("section",null,React.createElement("h2",null,title),children);
        export const PanelSectionRow=({children})=>React.createElement("div",{className:"row"},children);
        export const ButtonItem=({children,onClick,disabled})=>React.createElement("button",{onClick,disabled},children);
        export const Navigation={NavigateToExternalWeb:url=>window.supportFixture.externalLinks.push(url)};
        export function showModal(content){
          const mount=document.createElement("div");document.body.appendChild(mount);
          const root=createRoot(mount);root.render(content);
          return {Close:()=>{root.unmount();mount.remove();}};
        }
        export const ConfirmModal=({strTitle,strDescription,strOKButtonText,onOK})=>React.createElement("div",{role:"dialog","aria-label":strTitle},React.createElement("h2",null,strTitle),strDescription,React.createElement("button",{onClick:onOK},strOKButtonText||"Done"));
      `}));
    }
  }]
});
