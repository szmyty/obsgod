# Build and qualify the Steam Deck preview

Use Go **1.27.4**, Node **24.19.0**, npm **11.9.0**, and Python **3.12+** for the
packaging/test environment. End users install the binary package and do not need
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
python3 scripts/package-deck.py --version 0.1.0-deck.2
```

The script uses the current full commit SHA and refuses a dirty checkout. For
local experimentation only, `--allow-dirty` creates a manifest explicitly marked
dirty. Do not publish that package. It produces the Deck archive, Decky ZIP,
manifest and SHA256SUMS under `dist/`. Repeating the same build from the same
revision/toolchain must produce identical checksums. It includes dependency
licenses and the preferred source for the separate LGPL Decky API module.

Browser tests use Playwright **1.62.0** and Chromium. They install into temporary
homes, use fixture credentials and extract the actual archive/ZIP:

```sh
python3 steamdeck/tests/browser-setup.py dist/obsgod-deck_0.1.0-deck.2_linux_amd64.tar.gz
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
loopback RTMP. A synthetic moving-video producer stands in for Gamescope and
restarts after consumer disconnects. This does not test Flatpak sandbox behavior,
SteamOS session changes, AMD hardware encoding, actual game capture or Kick.
The fixture disables gst-launch's debugger spin: its GStreamer 1.26 PipeWire sink
can fault during consumer teardown, and must exit so the supervisor can restart
it. A previous run exposed this fixture failure; OBSGod's rendered-frame gate
correctly refused to broadcast the blank feed. This is not a Gamescope repair.

The output directory contains redacted command results, media probes, rendered
pixels/frame hashes and audio measurements. It also tests start failure with no
receiver and checks that a later listener receives no unexpected connection.
No real credentials or external stream are used.

For optional read-only diagnostics against an already running OBS, set
`OBSGOD_TEST_OBS_ADDRESS` and `OBSGOD_TEST_OBS_PASSWORD` as environment variables
and run `go test ./pkg/automation -run TestRealOBSReadOnly -v`. Otherwise that test
is explicitly skipped. Never put a password or stream key into command arguments.

## Publication

Publish the exact clean revision and verified artifacts as a **prerelease** until
the [Steam Deck acceptance checklist](steam-deck.md#acceptance-on-your-deck) has
real-device evidence. Include source SHA, tool versions, commands, outcomes,
artifact checksums and remaining hardware/CI limits in the release evidence.
The broader v1 roadmap issues stay open until their full criteria are satisfied.
