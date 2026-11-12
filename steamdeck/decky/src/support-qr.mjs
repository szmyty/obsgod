import qrcode from "qrcode-generator";
import {validAddressFormat,walletDefinitions} from "./support.mjs";

// Encode only the configured public address, locally. A QR service must never
// receive stream settings or even be needed to display a receiving address.
export function addressQr(wallet) {
  const definition=walletDefinitions[wallet?.coin];
  if(!definition || wallet.network!==definition.network || !validAddressFormat(wallet.coin,wallet.address)) {
    throw new Error("Invalid receiving address.");
  }
  const code=qrcode(0,"M");
  code.addData(wallet.address,"Byte");
  code.make();
  return code.createDataURL(6,24);
}
