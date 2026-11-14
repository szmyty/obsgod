import {readFileSync,writeFileSync,mkdirSync,copyFileSync,existsSync,lstatSync,readdirSync} from "node:fs";
import {createRequire} from "node:module";
import {dirname,join,resolve,isAbsolute,parse} from "node:path";
import {fileURLToPath} from "node:url";
import ts from "typescript";
import externalGlobals from "rollup-plugin-external-globals";
import {generateSupport} from "../../scripts/generate-support.mjs";

// Keep the LGPL Decky API as a separate, replaceable module instead of inlining
// it into the MIT plugin. Steam supplies React and the Decky UI at runtime.
const require=createRequire(import.meta.url);
// Packaging builds use an owned private staging directory. Reject links and
// foreign output rather than changing permissions or repairing existing files.
const output=process.env.OBSGOD_FRONTEND_OUT??"dist";
if(process.env.OBSGOD_FRONTEND_OUT!==undefined){
  if(!isAbsolute(output)||resolve(output)!==output)throw new Error("Unsafe frontend output override");
  const parent=dirname(output),owner=lstatSync(parent),uid=process.getuid();
  if(!owner.isDirectory()||owner.isSymbolicLink()||owner.uid!==uid||(owner.mode&0o077))throw new Error("Frontend output requires a private owned parent");
  for(let path=parent;;path=dirname(path)){
    const info=lstatSync(path);
    if(!info.isDirectory()||info.isSymbolicLink())throw new Error("Unsafe frontend output ancestor");
    if(![0,uid].includes(info.uid)||((info.mode&0o022)&&!(info.mode&0o1000)))throw new Error("Unprotected or foreign frontend output ancestor");
    if(path===parse(path).root)break;
  }
}
function validateOutput(path){
  let info;try{info=lstatSync(path);}catch(error){if(error.code==="ENOENT")return;throw error;}
  if(info.isSymbolicLink()||info.uid!==process.getuid())throw new Error("Unsafe or foreign frontend output");
  if(info.isDirectory())for(const name of readdirSync(path))validateOutput(join(path,name));
  else if(!info.isFile()||info.nlink!==1)throw new Error("Non-regular or linked frontend output");
}
validateOutput(output);
generateSupport(fileURLToPath(new URL("../../",import.meta.url)));
const apiPath=require.resolve("@decky/api");
mkdirSync(output,{recursive:true});
writeFileSync(join(output,"decky-api.js"),readFileSync(apiPath,"utf8").replace("'@decky/manifest'","'./manifest.js'").replace('"./types"','"./types.js"'));
copyFileSync(join(dirname(apiPath),"types.js"),join(output,"types.js"));
writeFileSync(join(output,"manifest.js"),'export default {name:"OBSGod"};\n');
copyFileSync("LICENSE.qrcode-generator.txt",join(output,"LICENSE.qrcode-generator.txt"));

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
  output:{dir:output,format:"esm",exports:"default",paths:{"@decky/api":"./decky-api.js"}}
};
