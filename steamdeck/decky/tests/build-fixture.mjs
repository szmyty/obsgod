// Browser test runtime only. React is never copied into the release plugin.
import {build} from "esbuild";
await build({
  stdin:{contents:'import * as React from "react"; import * as JSX from "react/jsx-runtime"; import {createRoot} from "react-dom/client"; window.SP_REACT=React; window.SP_JSX=JSX; window.fixtureRoot=createRoot;',resolveDir:process.cwd()},
  outfile:process.argv[2],bundle:true,format:"iife",platform:"browser",minify:false
});
