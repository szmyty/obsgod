import {auroraIcon} from "./aurora-brand.mjs";

/** Decorative branding; live status is a separate observed-state element. */
export function AuroraMark({size=24}:{size?:number}){
  return <img data-brand="aurora" src={auroraIcon} width={size} height={size} alt="" aria-hidden="true" style={{display:"block",flexShrink:0}}/>;
}
