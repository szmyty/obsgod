# Build and qualify the Steam Deck preview

Use Go **1.27.4**, Node **24.19.0**, npm **11.9.0**, and Python **3.12+** for the
packaging/test environment. Packaging also requires a working local Docker
daemon to build the small app-filtered capture source against the pinned
bookworm builder in `steamdeck/capture/build.Dockerfile`. The compiler stage runs
without network; the image ID, package versions and symbol requirements are
recorded in `dist/capture-build.json`. End users install the binary package and do not need
Go, Node, npm or Docker. The Desktop helper uses the Deck's system Python 3.9+.

```sh
go mod download
npm --prefix steamdeck/decky ci --ignore-scripts
go test -race ./...
go vet ./...
python3 -m unittest discover -s steamdeck/tests -p 'test_*.py' -v
npm --prefix steamdeck/decky run typecheck
npm --prefix steamdeck/decky test
npm --prefix steamdeck/decky run build
npm --prefix steamdeck/decky audit
go install golang.org/x/vuln/cmd/govulncheck@v1.9.0
govulncheck ./...
```

Commit source before making a release candidate:

```sh
python3 scripts/package-deck.py --version 0.1.0-deck.9
```

The script uses the current full commit SHA and refuses a dirty checkout. For
local experimentation only, `--allow-dirty` creates a manifest explicitly marked
dirty. Do not publish that package. It produces the Deck archive, Decky ZIP,
manifest and SHA256SUMS under `dist/`. Repeating the same build from the same
revision/toolchain must produce identical checksums. It includes dependency
licenses and the preferred source for the separate LGPL Decky API module.

Build from a non-root-owned checkout. Under ACT, frontend typecheck/test/build
run as that checkout's owner through `scripts/frontend-command.py`; package-deck
uses the same helper for its nested frontend work. It gives each command private
HOME/TMPDIR paths and refuses symlinked, foreign-owned or unsafe generated
frontend output without altering it. Root tool installation and Go/native build
stages keep their existing identity. Normal-user npm commands above remain the
post-CI rebuild check; qualification covers both absent and reused frontend
output. Never recursively chown the checkout to hide an ownership failure.

Browser tests use Playwright **1.62.0** and Chromium. They install into temporary
homes, use fixture credentials and extract the actual archive/ZIP:

```sh
python3 steamdeck/tests/browser-setup.py dist/obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz
python3 steamdeck/tests/browser-setup.py dist/obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz --upgrade-from /path/to/obsgod-deck_0.1.0-deck.1_linux_amd64.tar.gz
python3 steamdeck/tests/browser-panel.py dist/obsgod-decky.zip
```

The panel test simulates the Decky API and Steam UI globals. It verifies actual
browser imports, rendering and status behavior, not controller/Steam integration.

## Real Linux OBS harness

`steamdeck/tests/obs-smoke.Dockerfile` uses a pinned Debian image. Build it using
your normal Docker networking. In managed cloud environments, preserve the
provided proxy and mount its CA as the `proxy_ca` build secret. The harness never
disables TLS verification. A normal local machine can mount its system CA bundle:

```sh
docker build --secret id=proxy_ca,src=/etc/ssl/certs/ca-certificates.crt \
  -f steamdeck/tests/obs-smoke.Dockerfile -t obsgod-obs-smoke .
```

Create a disposable, user-writable work directory outside your source tree. Put
the upstream obs-gstreamer source archive there as `gstreamer-source.tar.gz`:

- Source: `https://codeload.github.com/fzwoch/obs-gstreamer/tar.gz/b60942f8cd9d788c95ef7dee256f52e14bdf023e`
- SHA256: `566d547e83140d53a0aa22ed152cebc436725b47e4ead452e79cf250da531268`
- Revision: Flathub's v0.4.1 plugin source. It is built only for testing;
  the product installs the plugin through Flathub.

Build the candidate first, then mount its source and the disposable work directory:

```sh
docker run --rm --user 1000:1000 \
  --mount type=bind,src=/absolute/path/to/obsgod,dst=/src,readonly \
  --mount type=bind,src=/absolute/path/to/disposable-work,dst=/work \
  obsgod-obs-smoke dbus-run-session -- bash /src/steamdeck/tests/native-obs-smoke.sh
```

**The script deletes `/work/home`, `/work/runtime`, `/work/output`, and
`/work/plugin-src` at startup. Mount only disposable test data at `/work`.**

It replaces the Flatpak invocation with a local OBS launcher but uses real OBS,
WebSocket authentication, GStreamer, PipeWire, PulseAudio, x264/AAC, recording and
loopback RTMP. A stable synthetic moving-video producer stands in for Gamescope across
consumer reconnects. This does not test Flatpak sandbox behavior,
SteamOS session changes, AMD hardware encoding, actual game capture or Kick.
The video fixture keeps one synthetic PipeWire node across consumer reconnects.
The former GStreamer 1.26 test producer could destroy its node or stall during
consumer teardown; repeated recording/replay qualification exposed that fixture
race and the product correctly refused blank frames. The existing C producer
avoids that node-lifetime race while the product still uses the real OBS
GStreamer input and rendered-frame gate. This is not a Gamescope repair.

The output directory contains redacted command results, media probes, rendered
pixels/frame hashes and audio measurements. It also tests start failure with no
receiver and checks that a later listener receives no unexpected connection.
No real credentials or external stream are used.

For optional read-only diagnostics against an already running OBS, set
`OBSGOD_TEST_OBS_ADDRESS` and `OBSGOD_TEST_OBS_PASSWORD` as environment variables
and run `go test ./pkg/automation -run TestRealOBSReadOnly -v`. Otherwise that test
is explicitly skipped. Never put a password or stream key into command arguments.

## Unified installer and updater integration

The runtime archive includes its maintained updater, release discovery module,
Decky helper, setup and updater Desktop launchers. Build the optional standalone
updater from that exact clean runtime archive, without rebuilding the runtime:

```sh
python3 scripts/package-updater.py dist/obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz
```

Check discovery without changing the installation:

```sh
python3 /path/to/extracted/OBSGod-Updater/update.py --check --json --channel preview
```

The bottom panel button calls the same read-only release checker. Applying an
update is an explicit Desktop action after output is confirmed idle; use the
installed **Update OBSGod** Applications entry or bundled Desktop launcher.
Normal update skips a matching version; `--repair` explicitly reinstalls it.
Channels distinguish stable releases and previews, and ignore updater-only tags.
Only official repository assets or immutable same-repository artifact links are
accepted, with matching tagged source, manifest, platform and file hashes.
Historical preview 4 is discoverable but lacks unified installation and cannot
be automatically applied by this newer updater.

The protocol smoke uses the unmodified Decky 3.3.1 backend router/installer and
its actual frontend WebSocket router at revision
`ffd103b9c1a4ce5bf305e7c0998eda6e05457dad`. Keep these GPL test inputs outside the
product tree. The harness verifies their Git blob identities and downloads the
pinned frontend router if it is absent from that directory. It holds the actual
frontend connection open while the compiled helper probes, installs/reinstalls,
and verifies the plugin and unrelated order/prompts:

```sh
python3 steamdeck/tests/decky-transport-smoke.py dist/decky-install dist/obsgod-decky.zip \
  --upstream /path/to/pinned-decky-sources \
  --runtime-archive dist/obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz \
  --previous-archive /path/to/obsgod-deck_0.1.0-deck.1_linux_amd64.tar.gz \
  --updater-zip dist/obsgod-one-click-update_0.1.0-deck.9_linux_amd64.zip
```

The full-archive options execute the real unified installer twice and check
configuration/key/media/history/other-plugin preservation. The fixture still
substitutes CDP forwarding, ownership operations, loader lifecycle, dialogs,
Flatpak info and the surrounding Steam window. It cannot qualify real SteamOS
or its Decky service. `updater-smoke.py` belongs to the historical updater-4
second-WebSocket protocol; it is not the Roadmap 1 candidate harness.

The updater option executes the unmodified extracted Desktop/file-URI launcher.
A disposable Python startup fixture supplies only exact canonical release/tag,
checksum, manifest and archive HTTP responses. Real discovery, hashing,
extraction and unified installation still execute, including no-update,
explicit same-version repair and a corrupted download that preserves the
existing installation. This is a network fixture, not a published release or
an actual Steam frontend.

The browser setup harness explicitly requests app-only installation to isolate
its Desktop entry/setup/clipboard path. Full Decky installation is exercised by
the separate pinned-transport integration above. Keep those evidence claims
separate. The native OBS harness likewise does not test Flatpak's actual
sandbox or Gamescope's real Steam UI capture.

## Candidate and publication gates

At the final clean source revision run the full applicable command matrix,
browser checks, native OBS, pinned Decky transport and updater integration.
Build both packages twice and compare SHA256SUMS and UPDATER-SHA256SUMS. Keep
source revision, harness revision, tool/platform versions, exact commands and
outcomes in candidate qualification evidence. Label optional skipped tests,
compilation-only platforms and unavailable real-device/CI checks explicitly.

`.github/workflows/steam-deck.yml` provides a pinned Linux validation/package
workflow and uploads review artifacts only; it never publishes a release or
changes deployments. Existing snapshot workflows were inspected for publishing
side effects. Missing workflow runs are not passing CI evidence.

Draft PR checkpoints are review artifacts. Do not publish the candidate or
merge/close its acceptance issues without owner review and required evidence.
A release publication is a separate action from building or uploading a draft
review artifact. All broader v1 and Roadmap 2 requirements remain separate.

## Completion candidate checks

Candidate 9 adds stream-only microphone controls and a versioned public API.
Run both new browser harnesses against the packaged assets:

```sh
python3 steamdeck/tests/browser-mixer-panel.py dist/obsgod-decky.zip
python3 steamdeck/tests/browser-mixer-setup.py dist/obsgod-deck_0.1.0-deck.9_linux_amd64.tar.gz
python3 -m unittest discover -s scripts/tests -p 'test_*.py' -v
python3 scripts/release-audit.py --revision "$(git rev-parse HEAD)" --output dist/supply-chain
```

See [local CI](local-ci.md) for pinned `act` jobs and limitations,
[release engineering](release-engineering.md) for unsigned SBOM/provenance
evidence, and the [completion review](completion-review.md) for the remaining
owner and physical-device checks. Local jobs do not establish hosted CI or
actual Steam Deck acceptance.
