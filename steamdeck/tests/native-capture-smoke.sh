#!/usr/bin/env bash
# Synthetic PipeWire protocol/media qualification of the *packaged* game source.
# Does not run real Gamescope, SteamOS, Flatpak, OBS scenes or a real game.
# Run in obs-smoke.Dockerfile's disposable container as uid1000, /src read-only.
set -euo pipefail
test -f /.dockerenv || { echo 'Use the disposable capture test container.' >&2; exit 2; }
test "$#" -eq 1 || { echo 'Pass the directory containing the packaged capture library.' >&2; exit 2; }
plugin_dir=$(realpath "$1")
test -f "$plugin_dir/libgstobsgodcapture.so"
test -d /work
umask 077
mkdir -p /work/capture-validation
out=/work/capture-validation
export HOME=${HOME:-/work/home}
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/work/runtime}
mkdir -p "$HOME" "$XDG_RUNTIME_DIR"
chmod 700 "$XDG_RUNTIME_DIR"
export GST_PLUGIN_PATH="$plugin_dir"
export GST_REGISTRY="$out/gst-registry.bin"
fixture_pid=''
duplicate_pid=''
pipewire_pid=''
wireplumber_pid=''
cleanup() {
  for pid in "$duplicate_pid" "$fixture_pid" "$wireplumber_pid" "$pipewire_pid"; do
    if test -n "$pid"; then kill "$pid" 2>/dev/null || true; wait "$pid" 2>/dev/null || true; fi
  done
}
trap cleanup EXIT

gcc -O2 -Wall -Wextra -Werror -o "$out/capture-fixture" \
  /src/steamdeck/tests/capture-fixture.c $(pkg-config --cflags --libs libpipewire-0.3)
gst-inspect-1.0 obsgodgamescopesrc > "$out/plugin-inspect.txt"
python3 - "$out/plugin-inspect.txt" "$plugin_dir/libgstobsgodcapture.so" <<'PY'
import pathlib,re,sys
text=pathlib.Path(sys.argv[1]).read_text()
match=re.search(r'^\s*Filename\s+(\S+)\s*$',text,re.M)
assert match and pathlib.Path(match[1]).resolve()==pathlib.Path(sys.argv[2]).resolve(),text
PY

if test "${CAPTURE_EXISTING_PIPEWIRE:-0}" != 1; then
  pipewire > "$out/pipewire.log" 2>&1 &
  pipewire_pid=$!
  for n in {1..50}; do
    if timeout 1 pw-dump > "$out/pipewire-ready.json" 2>/dev/null; then break; fi
    kill -0 "$pipewire_pid"
    sleep .1
  done
  timeout 1 pw-dump > "$out/pipewire-ready.json"
  wireplumber > "$out/wireplumber.log" 2>&1 &
  wireplumber_pid=$!
  for n in {1..50}; do
    timeout 1 pw-dump > "$out/wireplumber-ready.json"
    if python3 - "$out/wireplumber-ready.json" "$wireplumber_pid" <<'PY'
import json,sys
nodes=json.load(open(sys.argv[1]))
raise SystemExit(0 if any(str((x.get('info')or{}).get('props',{}).get('application.process.id'))==sys.argv[2] for x in nodes) else 1)
PY
    then break; fi
    kill -0 "$wireplumber_pid"
    sleep .1
  done
fi

start_fixture() {
  local mode=$1 case_name=$2
  if test -n "$fixture_pid"; then kill "$fixture_pid" 2>/dev/null || true; wait "$fixture_pid" || true; fixture_pid=''; fi
  target="obsgod-fixture-$case_name"
  "$out/capture-fixture" "$target" "$mode" > "$out/$case_name-producer.stdout" 2> "$out/$case_name-producer.log" &
  fixture_pid=$!
  for n in {1..50}; do
    timeout 1 pw-dump > "$out/$case_name-nodes.json"
    if python3 - "$out/$case_name-nodes.json" "$target" <<'PY'
import json,sys
raise SystemExit(0 if any((x.get('info')or{}).get('props',{}).get('node.name')==sys.argv[2] for x in json.load(open(sys.argv[1]))) else 1)
PY
    then return 0; fi
    kill -0 "$fixture_pid"
    sleep .1
  done
  echo 'Synthetic capture node did not register.' >&2
  return 1
}

capture() {
  local case_name=$1 appid=$2 count=$3
  timeout --signal=TERM --kill-after=2 12 gst-launch-1.0 --no-fault -q \
    obsgodgamescopesrc target-object="$target" app-id="$appid" stale-ms=300 num-buffers="$count" \
    ! filesink location="$out/$case_name.bgrx" \
    > "$out/$case_name-client.stdout" 2> "$out/$case_name-client.log"
}

start_fixture good game-a
capture game-a 4242 30
start_fixture good game-b
capture game-b 4243 30
start_fixture stale stale
capture stale 4242 60
start_fixture corrupt corrupt
capture corrupt 4242 30
start_fixture empty empty
capture empty 4242 30
start_fixture short short
set +e
capture short 4242 30
short_result=$?
set -e
printf '%s\n' "$short_result" > "$out/short-exit.txt"
test "$short_result" -ne 124 && test "$short_result" -ne 137

for mode in missing wrong zero mixed-dma; do
  start_fixture "$mode" "reject-$mode"
  set +e
  capture "reject-$mode" 4242 5
  result=$?
  set -e
  printf '%s\n' "$result" > "$out/reject-$mode-exit.txt"
  test "$result" -ne 0 && test "$result" -ne 124
  test ! -s "$out/reject-$mode.bgrx"
done
for appid in 0 769; do
  start_fixture good "reject-id-$appid"
  set +e
  capture "reject-id-$appid" "$appid" 5
  result=$?
  set -e
  printf '%s\n' "$result" > "$out/reject-id-$appid-exit.txt"
  test "$result" -ne 0 && test "$result" -ne 124
  test ! -s "$out/reject-id-$appid.bgrx"
done

# The target name is not an identity. After valid media is flowing, a second
# source with the same name must invalidate capture rather than retarget it.
start_fixture good late-duplicate
set +e
capture late-duplicate 4242 150 &
consumer_pid=$!
set -e
for n in {1..50}; do
  if test -s "$out/late-duplicate.bgrx"; then break; fi
  kill -0 "$consumer_pid"
  sleep .05
done
test -s "$out/late-duplicate.bgrx"
"$out/capture-fixture" "$target" missing > "$out/duplicate-producer.stdout" 2> "$out/duplicate-producer.log" &
duplicate_pid=$!
set +e
wait "$consumer_pid"
duplicate_result=$?
set -e
printf '%s\n' "$duplicate_result" > "$out/late-duplicate-exit.txt"
test "$duplicate_result" -ne 0 && test "$duplicate_result" -ne 124 && test "$duplicate_result" -ne 137
kill "$duplicate_pid" 2>/dev/null || true
wait "$duplicate_pid" || true
duplicate_pid=''

python3 - "$out" "$plugin_dir/libgstobsgodcapture.so" <<'PY'
import hashlib,json,os,pathlib,subprocess,sys
p=pathlib.Path(sys.argv[1]);size=320*180*4
results={}
for name,channel in [('game-a',2),('game-b',1)]:
 data=(p/f'{name}.bgrx').read_bytes()
 assert data and len(data)%size==0,(name,len(data))
 frames=[data[i:i+size] for i in range(0,len(data),size)]
 colored=[f for f in frames if max(f[0::4]+f[1::4]+f[2::4])>0]
 assert colored,(name,'no game frames')
 for frame in colored:
  means=[sum(frame[c::4])/(320*180) for c in range(3)]
  assert means[channel]>150 and means[0]<40,(name,means,'compositor/unselected content')
 assert len({hashlib.sha256(f).hexdigest() for f in colored})>1,(name,'game video did not move')
 log=(p/f'{name}-producer.log').read_text()
 assert f'"appid":{4242 if name=="game-a" else 4243}' in log,(name,log)
 results[name]={'frames':len(frames),'moving_game_frames':len(colored),'blue_compositor_frames':0}
for name in ['corrupt','empty','short']:
 data=(p/f'{name}.bgrx').read_bytes()
 assert len(data)%size==0,(name,len(data))
 if name in ['corrupt','empty']:assert data,(name,'source emitted no valid fallback frames')
 assert not any(data[c::4].strip(b'\0') for c in range(3)),(name,'invalid media copied')
 results[name]={'frames':len(data)//size,'result':'invalid chunks excluded; black or bounded error'}
data=(p/'stale.bgrx').read_bytes();assert len(data)>=30*size and len(data)%size==0
frames=[data[i:i+size] for i in range(0,len(data),size)]
assert any(max(f[2::4])>150 for f in frames[:15]),'stale case never received a game frame'
assert all(not any(f[c::4].strip(b'\0') for c in range(3)) for f in frames[-10:]),'stale game frame was retained'
results['stale']={'frames':len(frames),'last_ten_frames':'black'}
data=(p/'late-duplicate.bgrx').read_bytes();assert data and len(data)%size==0
frames=[data[i:i+size] for i in range(0,len(data),size)]
assert any(max(f[2::4])>150 for f in frames),'duplicate case did not begin with actual game media'
for frame in frames:
 means=[sum(frame[c::4])/(320*180) for c in range(3)]
 assert means[0]<40,('late duplicate exposed blue compositor',means)
results['late-duplicate']={'frames_before_failure':len(frames),'exit_code':int((p/'late-duplicate-exit.txt').read_text()),'blue_compositor_frames':0}
for name in ['missing','wrong','zero','mixed-dma','id-0','id-769']:
 code=int((p/f'reject-{name}-exit.txt').read_text())
 assert code not in (0,124),(name,code)
 results[f'reject-{name}']={'exit_code':code,'media_bytes':0}
proof={'state':'passed','scope':'Synthetic PipeWire custom-SPA negotiation and supplied GStreamer source CPU media; not real Gamescope, SteamOS, Flatpak or OBS scene transitions',
 'source_revision':os.environ.get('OBSGOD_QUALIFIED_REVISION','unrecorded development run'),
 'plugin_path':sys.argv[2],'plugin_sha256':hashlib.sha256(pathlib.Path(sys.argv[2]).read_bytes()).hexdigest(),
 'fixture_source_sha256':hashlib.sha256(pathlib.Path('/src/steamdeck/tests/capture-fixture.c').read_bytes()).hexdigest(),
 'test_source_sha256':hashlib.sha256(pathlib.Path('/src/steamdeck/tests/native-capture-smoke.sh').read_bytes()).hexdigest(),
 'platform':list(os.uname()),
 'pipewire':subprocess.check_output(['pw-cli','--version'],text=True).strip(),
 'gstreamer':subprocess.check_output(['gst-launch-1.0','--version'],text=True).strip(),
 'cases':results}
(p/'qualification.json').write_text(json.dumps(proof,indent=2)+'\n')
print('PASS: app-scoped negotiation/media; distinct moving game patterns; no compositor frames; stale/corrupt/EMPTY black; malformed chunk, unsupported/wrong/zero/Steam appid, mixed-DMA capability and late duplicate fail closed. Synthetic producer only.')
PY
