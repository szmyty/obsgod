// Settings RPCs must finish their backend command, cleanup and readback before
// these UI bounds. Expiry means unconfirmed, never cancellation or success.
export const settingsTimeouts=Object.freeze({captureMode:15000,configurationRead:12000,configurationAction:20000});

/** @template T
 * @param {Promise<T>} promise
 * @param {number} milliseconds
 * @param {string} [message]
 * @returns {Promise<T>}
 */
export function boundedRequest(promise,milliseconds,message="Operation timed out"){
  return new Promise((resolve,reject)=>{
    const timer=setTimeout(()=>reject(new Error(message)),milliseconds);
    promise.then(value=>{clearTimeout(timer);resolve(value);},error=>{clearTimeout(timer);reject(error);});
  });
}
