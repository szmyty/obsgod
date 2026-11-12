import {readFileSync,writeFileSync,mkdirSync,copyFileSync,existsSync} from "node:fs";
import {createRequire} from "node:module";
import {dirname,join,resolve} from "node:path";
import {fileURLToPath} from "node:url";
import ts from "typescript";
import externalGlobals from "rollup-plugin-external-globals";
import {generateSupport} from "../../scripts/generate-support.mjs";

// Keep the LGPL Decky API as a separate, replaceable module instead of inlining
// it into the MIT plugin. Steam supplies React and the Decky UI at runtime.
const require=createRequire(import.meta.url);
generateSupport(fileURLToPath(new URL("../../",import.meta.url)));
const apiPath=require.resolve("@decky/api");
mkdirSync("dist",{recursive:true});
writeFileSync("dist/decky-api.js",readFileSync(apiPath,"utf8").replace("'@decky/manifest'","'./manifest.js'").replace('"./types"','"./types.js"'));
copyFileSync(join(dirname(apiPath),"types.js"),"dist/types.js");
writeFileSync("dist/manifest.js",'export default {name:"OBSGod"};\n');
copyFileSync("LICENSE.qrcode-generator.txt","dist/LICENSE.qrcode-generator.txt");

export default {
  input:"src/index.tsx",
  external:["@decky/api","react","react/jsx-runtime","@decky/ui"],
  plugins:[
    {name:"local-typescript",resolveId(id,importer){
      if(importer && id.startsWith("."))for(const extension of [".tsx",".ts"]) {
        const candidate=resolve(dirname(importer),id)+extension;
        if(existsSync(candidate))return candidate;
      }
    }},
    {name:"local-qr",resolveId(id){if(id==="qrcode-generator")return fileURLToPath(import.meta.resolve(id));}},
    {name:"typescript",transform(code,id){if(id.endsWith(".tsx")||id.endsWith(".ts"))return {code:ts.transpileModule(code,{compilerOptions:{jsx:ts.JsxEmit.ReactJSX,module:ts.ModuleKind.ESNext,target:ts.ScriptTarget.ES2020}}).outputText,map:null};}},
    externalGlobals({react:"SP_REACT","react/jsx-runtime":"SP_JSX","@decky/ui":"DFL"})
  ],
  output:{dir:"dist",format:"esm",exports:"default",paths:{"@decky/api":"./decky-api.js"}}
};
