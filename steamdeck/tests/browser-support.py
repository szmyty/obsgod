#!/usr/bin/env python3
"""Exercise configured receiving dialogs using public test inputs only.

The compiled fixture imports actual Support/model/QR source. It substitutes the
Decky UI host, not receiving behavior, and does not edit product recipients.
"""
import argparse
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import subprocess
import tempfile
import threading
from playwright.sync_api import sync_playwright


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *_):
        pass


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--browser",default="/usr/bin/chromium")
    parser.add_argument("--screenshots",type=Path,default=Path("/tmp/decky-stream-support"))
    args=parser.parse_args()
    args.screenshots.mkdir(parents=True,exist_ok=True)
    decky=Path(__file__).resolve().parents[1]/"decky"
    with tempfile.TemporaryDirectory(prefix="decky-stream-support-") as directory:
        root=Path(directory)
        subprocess.run(["node","tests/build-support-fixture.mjs",str(root/"runtime.js")],cwd=decky,check=True)
        (root/"index.html").write_text('''<!doctype html><html><head><meta charset="utf-8"><title>Receiving dialog fixture</title><style>body{margin:0;background:#111923;color:#f0f3fc;font:15px system-ui}#root,[role=dialog]{width:330px;max-width:calc(100vw - 28px);padding:14px;margin:0 auto}button{display:block;width:100%;padding:12px;margin:8px 0;background:#354765;color:white;border:0;font:inherit}button:focus{outline:3px solid #86d5ff}</style></head><body><div id="root"></div><script src="runtime.js"></script></body></html>''')
        server=ThreadingHTTPServer(("127.0.0.1",0),partial(QuietHandler,directory=str(root)))
        thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
        try:
            with sync_playwright() as p:
                browser=p.chromium.launch(executable_path=args.browser,headless=True,args=["--no-sandbox"])
                page=browser.new_page(viewport={"width":800,"height":900})
                page.context.grant_permissions(["clipboard-read","clipboard-write"])
                errors=[];requests=[]
                page.on("pageerror",lambda error:errors.append(str(error)))
                page.on("request",lambda request:requests.append(request.url))
                origin="http://127.0.0.1:"+str(server.server_port)
                page.goto(origin)
                for coin,label,network in [
                    ("bitcoin","Bitcoin","Bitcoin Mainnet"),
                    ("ethereum","Ethereum","Ethereum Mainnet"),
                    ("solana","Solana","Solana Mainnet Beta"),
                ]:
                    page.get_by_role("button",name="Support with "+label,exact=True).click()
                    dialog=page.get_by_role("dialog",name="Support with "+label,exact=True)
                    dialog.wait_for()
                    dialog.get_by_text(network,exact=True).wait_for()
                    address=page.evaluate("coin=>supportFixture.examples.wallets[coin].address",coin)
                    assert dialog.get_by_label(label+" receiving address",exact=True).inner_text()==address
                    qr=dialog.get_by_role("img",name=label+" public receiving address QR code",exact=True)
                    assert qr.get_attribute("src").startswith("data:image/gif;base64,")
                    qr.evaluate("image=>image.decode()")
                    assert qr.evaluate("image=>image.naturalWidth>0&&image.naturalHeight>0")
                    copy=dialog.get_by_role("button",name="Copy address",exact=True)
                    copy.click()
                    dialog.get_by_text("Address copied.",exact=False).wait_for()
                    assert page.evaluate("navigator.clipboard.readText()") == address
                    assert copy.evaluate("button=>document.activeElement===button")
                    if coin=="ethereum":
                        page.screenshot(path=str(args.screenshots/"ethereum-receive-test-input.png"),full_page=True)
                        # Denied asynchronous access must use the fallback and
                        # never claim success when both clipboard paths fail.
                        page.evaluate("""supportFixture.readClipboard=navigator.clipboard.readText.bind(navigator.clipboard);
                          Object.defineProperty(navigator,'clipboard',{configurable:true,value:{writeText:async()=>{throw Error('fixture denied')}}});""")
                        copy.click()
                        dialog.get_by_text("Address copied.",exact=False).wait_for()
                        assert page.evaluate("supportFixture.readClipboard()") == address
                        page.evaluate("document.execCommand=()=>false")
                        copy.click()
                        dialog.get_by_text("Clipboard unavailable.",exact=False).wait_for()
                        assert copy.evaluate("button=>document.activeElement===button")
                    dialog.get_by_role("button",name="Done",exact=True).click()
                    dialog.wait_for(state="detached")
                    if coin=="ethereum":
                        page.reload()
                assert not page.evaluate("supportFixture.externalLinks")
                assert all(url.startswith(origin) for url in requests),requests
                assert not errors,errors
                browser.close()
            print("PASS: actual receiving component with Bitcoin/Ethereum/Solana public test inputs; explicit networks/full addresses, locally rendered QR images, exact clipboard contents, fallback/failure honesty, focus preservation, dialog close, zero external requests. Production recipients unchanged. Real Steam/Decky modal/controller and wallet scanning remain unrun.")
        finally:
            server.shutdown();server.server_close();thread.join()


if __name__=="__main__":
    main()
