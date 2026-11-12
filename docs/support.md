# Optional development support

The bottom of the Decky panel offers optional external support links. Starting,
stopping, configuring and recovering a stream never requires a contribution or
a support account. Opening a support link is an explicit action; link or network
failure does not change the stream. The plugin does not record support clicks or
receive payment information.

## Provider configuration

`.github/FUNDING.yml` is the source for both GitHub's Sponsor menu and the
packaged provider buttons. The initial handles match the owner's shared funding
configuration in `egohygiene/akashic` at
`dc21c6a24506d748deb45f29ce54fc7e7bf69753`. Five destinations are configured:
GitHub Sponsors, Buy Me a Coffee, Ko-fi, Open Collective and thanks.dev. The
source records an inactive Patreon creator page, so Patreon is not enabled.
Existing configuration establishes intended recipient handles; it does not prove
current payout eligibility or that a payment was successfully received.

Use flat scalar handles for the five supported providers. GitHub additionally
accepts an inline or indented list of handles. Unsupported active providers,
duplicates and other YAML features fail generation rather than silently changing
where a button sends someone. Provider URLs come from fixed HTTPS templates, not
arbitrary configuration URLs. Adding a provider requires a reviewed template and
controller-accessible label.

After editing funding or wallet configuration, run:

```sh
node scripts/generate-support.mjs
node scripts/generate-support.mjs --check
npm --prefix steamdeck/decky test
npm --prefix steamdeck/decky run build
```

Commit the configuration and generated `steamdeck/decky/src/support-data.mjs`
together. Generation is deterministic and runs without network access. Release
packaging checks that the generated data matches its sources; building refreshes
it. Installed plugins do not fetch funding data from another repository.

## Optional cryptocurrency receiving addresses

`support.json` contains disabled Bitcoin, Ethereum and Solana entries with
`address: null`. They are hidden in the normal panel. To enable one, the owner
sets its public receiving address and confirms the explicit supported network:

| Asset | Network value | User-visible network |
| --- | --- | --- |
| Bitcoin | `bitcoin-mainnet` | Bitcoin Mainnet |
| Ethereum | `ethereum-mainnet` | Ethereum Mainnet |
| Solana | `solana-mainnet-beta` | Solana Mainnet Beta |

Only put **public receiving addresses** here. This file is shipped publicly;
never put seed phrases, private keys, exchange API credentials or stream keys in
it. Leave an address null when the wallet is not ready. Testnet and alternative
chains are not supported by these entries. An Ethereum-format address on another
chain does not make that chain supported.

Before enabling an address, the owner must verify it in their own wallet and
verify the destination/network end to end. The build rejects unknown schema
versions, unsupported networks, extra wallet fields and malformed address
formats. These are format checks, **not checksum, ownership, balance or payment
verification**. Bitcoin entries accept lowercase `bc1` and legacy `1`/`3`
formats; Ethereum requires `0x` plus 40 hexadecimal digits; Solana requires a
Base58 address format. A syntactically valid address can still be the wrong
recipient. Never treat a successful build as proof of wallet ownership.

Once configured, the receiving dialog shows the asset/network, full selectable
address, a copy button and an address QR generated locally. The QR contains the
public address only, with no amount or payment request. The plugin does not
connect wallets, sign transactions, hold funds or send data to a QR service.
The sender verifies the destination and network in their wallet before sending.
Clipboard failure leaves the address and QR available.

## Distribution and evidence

Public support destinations and device/browser navigation still require owner
verification before a supported release. No donation, account creation or
transaction was performed while implementing this feature. Actual contributions
and payout readiness must not be inferred from a configured link or local test.
Decky Store admission and support-link rules remain their own external gate;
direct distribution does not establish Store acceptance.

The local QR implementation is `qrcode-generator` 2.0.4 by Kazuhiko Arase under
MIT. Its complete license is shipped in `LICENSE.qrcode-generator.txt`; the
symbols used in the support buttons are neutral text symbols, not copied provider
logos.
