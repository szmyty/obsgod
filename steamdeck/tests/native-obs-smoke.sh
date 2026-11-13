#!/usr/bin/env bash
# Run inside obs-smoke.Dockerfile as uid 1000, with /src and writable /work.
# This is synthetic Linux OBS qualification, never Steam Deck hardware evidence.
set -euo pipefail
ulimit -c 0
test -f /.dockerenv || { echo 'Run this harness only in its disposable Docker container.' >&2; exit 2; }
# Every run gets a fresh fixture; persistent PulseAudio/Wayland socket and pid
# files from a previous container must not impersonate a running daemon.
rm -rf /work/home /work/runtime /work/output /work/plugin-src
export HOME=/work/home XDG_CONFIG_HOME=/work/home/.config XDG_RUNTIME_DIR=/work/runtime
export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 QT_X11_NO_MITSHM=1
export PATH=/work/bin:$PATH
umask 077
mkdir -p "$HOME" "$XDG_RUNTIME_DIR" /work/bin /work/output
chmod 700 "$XDG_RUNTIME_DIR"
cleanup() {
  ffmpeg -v error -f x11grab -video_size 1280x800 -i :99 -frames:v 1 -y /work/output/desktop.png >/dev/null 2>&1 || true
  jobs -pr | xargs -r kill 2>/dev/null || true
}
trap cleanup EXIT
Xvfb :99 -screen 0 1280x800x24 -ac >/work/xvfb.log 2>&1 &

wait_for_fixture_service() {
  local fixture_service=$1 fixture_pid=$2 fixture_log=$3
  shift 3
  for attempt in {1..50}; do
    if ! kill -0 "$fixture_pid" 2>/dev/null; then
      echo "$fixture_service exited during fixture startup; inspect $fixture_log" >&2
      return 1
    fi
    if "$@" >/dev/null 2>&1; then return 0; fi
    sleep .2
  done
  echo "$fixture_service did not become ready within the bounded fixture startup wait; inspect $fixture_log" >&2
  return 1
}

wireplumber_connected() {
  timeout 1 pw-dump >/work/output/wireplumber-ready.json || return 1
  python3 - "$wireplumber_pid" /work/output/wireplumber-ready.json <<'PY'
import json,sys
nodes=json.load(open(sys.argv[2]))
connected=any(
 node.get('type')=='PipeWire:Interface:Client' and
 str((node.get('info') or {}).get('props',{}).get('application.process.id'))==sys.argv[1] and
 ((node.get('info') or {}).get('props',{}).get('application.name','').casefold()=='wireplumber' or
  (node.get('info') or {}).get('props',{}).get('application.process.binary')=='wireplumber')
 for node in nodes)
raise SystemExit(0 if connected else 1)
PY
}

# WirePlumber can exit if its first connection races PipeWire startup. Require
# the server first, then the live session-manager client, then PulseAudio.
pipewire >/work/pipewire.log 2>&1 &
pipewire_pid=$!
wait_for_fixture_service PipeWire "$pipewire_pid" /work/pipewire.log timeout 1 pw-dump
wireplumber >/work/wireplumber.log 2>&1 &
wireplumber_pid=$!
wait_for_fixture_service WirePlumber "$wireplumber_pid" /work/wireplumber.log wireplumber_connected
pulseaudio --daemonize=no --exit-idle-time=-1 >/work/pulse.log 2>&1 &
pulse_pid=$!
wait_for_fixture_service PulseAudio "$pulse_pid" /work/pulse.log timeout 1 pactl info
pactl load-module module-null-sink sink_name=obsgod_game >/dev/null
pactl load-module module-null-sink sink_name=obsgod_decoy >/dev/null
# A tagged game's actual sink must win over an unrelated default sink. Distinct
# tones make a wrong route detectable in the encoded recording/RTMP samples.
pactl set-default-sink obsgod_decoy
(
  while true; do
    # GStreamer 1.26's synthetic PipeWire sink can fault on consumer teardown.
    # Disable its debugger spin so this disposable fixture actually exits and
    # the supervisor can restart it. Gamescope itself is not this gst process.
    gst-launch-1.0 --no-fault -q videotestsrc is-live=true pattern=ball ! video/x-raw,width=1280,height=800,framerate=30/1 ! pipewiresink mode=provide 'stream-properties=props,node.name=gamescope,media.class=Video/Source' >>/work/video-producer.log 2>&1 || true
    sleep .2
  done
) &
env SteamAppId=424242 SteamGameId=424242 gst-launch-1.0 -q audiotestsrc is-live=true wave=sine freq=440 volume=0.2 ! audioconvert ! pulsesink device=obsgod_game >/work/audio-producer.log 2>&1 &
game_audio_pid=$!
gst-launch-1.0 -q audiotestsrc is-live=true wave=sine freq=880 volume=0.2 ! audioconvert ! pulsesink device=obsgod_decoy >/work/decoy-audio-producer.log 2>&1 &
decoy_audio_pid=$!

audio_input_state() {
  timeout 1 pactl --format=json list sink-inputs >/work/output/audio-inputs.json || return 1
  python3 - "$1" "$2" /work/output/audio-inputs.json <<'PY'
import json,sys
inputs=json.load(open(sys.argv[3]))
found=any(str(value.get('properties',{}).get('application.process.id'))==sys.argv[1] for value in inputs)
raise SystemExit(0 if found==(sys.argv[2]=='present') else 1)
PY
}
audio_input_present() { audio_input_state "$1" present; }
audio_input_absent() { audio_input_state "$1" absent; }
wait_for_fixture_service GameTone "$game_audio_pid" /work/audio-producer.log audio_input_present "$game_audio_pid"
wait_for_fixture_service DecoyTone "$decoy_audio_pid" /work/decoy-audio-producer.log audio_input_present "$decoy_audio_pid"

# Prove the media detector rejects digital silence; a finite -91dB volume value
# is not by itself evidence of sound. No product output is relabeled by this.
ffmpeg -v error -f lavfi -i anullsrc=r=48000:cl=mono -t 1 -c:a pcm_s16le -y /work/output/silence.wav
python3 /src/steamdeck/tests/native-audio.py measure /work/output/silence.wav 440 --silent >/work/output/silence-negative-control.json

# Replace only the Flatpak invocation in this disposable container. Model its
# post-option XDG reset so a pre-sandbox --env override cannot falsely qualify
# managed configuration. Capture, audio, OBS and WebSocket traffic remain real.
cat > /work/bin/flatpak <<'PY'
#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
if args[0]=='info': raise SystemExit(0)
if args[0]!='run': raise SystemExit(2)
for arg in args[1:]:
 if arg.startswith('--env='):
  key,value=arg[6:].split('=',1);os.environ[key]=value
index=args.index('com.obsproject.Studio')
os.environ['XDG_CONFIG_HOME']=os.path.join(os.environ['HOME'],'.var/app/com.obsproject.Studio/config')
command=next((arg.split('=',1)[1] for arg in args[1:index] if arg.startswith('--command=')),'obs')
os.execvp(command,[command]+args[index+1:])
PY
chmod 700 /work/bin/flatpak
ordinary="$HOME/.var/app/com.obsproject.Studio/config/obs-studio"
mkdir -p "$ordinary"
printf '%s\n' 'ordinary OBS configuration must remain unchanged' > "$ordinary/preserve.txt"

# Build upstream's exact Flathub source revision, kept outside the product.
mkdir -p /work/plugin-src
tar xf /work/gstreamer-source.tar.gz -C /work/plugin-src --strip-components=1
printf '%s\n' 'const char *obs_gstreamer_version = "v0.4.1-smoke";' > /work/plugin-src/version.c
plugin="$HOME/.var/app/com.obsproject.Studio/config/obsgod/obs-studio/plugins/obs-gstreamer/bin/64bit"
mkdir -p "$plugin"
gcc -shared -fPIC -O2 -o "$plugin/obs-gstreamer.so" /work/plugin-src/gstreamer*.c /work/plugin-src/version.c $(pkg-config --cflags --libs libobs gstreamer-app-1.0 gstreamer-audio-1.0 gstreamer-video-1.0 gstreamer-net-1.0)
printf '%s\n' '{"version":1,"server":"rtmp://127.0.0.1:1935/live","stream_key":"fixture-key","bitrate":3000,"fps":30,"encoder":"x264","microphone":false,"capture_mode":"screen"}' | /src/dist/obsgod deck configure > /work/output/configure.json
pw-dump > /work/output/pipewire-nodes.json
/src/dist/obsgod deck test-recording > /work/output/test-recording.json
python3 /src/steamdeck/tests/native-audio.py snapshot obsgod_game.monitor >/work/output/audio-route-recording.json
clip=$(python3 -c 'import json;print(json.load(open("/work/output/test-recording.json"))["recording_path"])')
ffprobe -v error -show_streams -show_format -of json "$clip" > /work/output/recording-probe.json
ffmpeg -v error -ss 2 -i "$clip" -frames:v 1 -y /work/output/capture.png
ffmpeg -v error -ss 2 -i "$clip" -frames:v 1 -f rawvideo -pix_fmt rgb24 -y /work/output/frame.rgb
ffmpeg -v error -ss 1 -i "$clip" -an -vf fps=1 -frames:v 3 -f framemd5 -y /work/output/frames.md5
ffmpeg -hide_banner -i "$clip" -af volumedetect -vn -f null - >/work/output/recording-audio.txt 2>&1
ffmpeg -v error -ss 1 -i "$clip" -t 2 -vn -ar 48000 -ac 1 -c:a pcm_s16le -y /work/output/recording-audio.wav
python3 /src/steamdeck/tests/native-audio.py measure /work/output/recording-audio.wav 440 >/work/output/recording-audio-metrics.json
OBSGOD_DISPOSABLE_MEDIA_FIXTURE=1 python3 /src/steamdeck/tests/native-media.py > /work/output/native-media-summary.json
python3 /src/steamdeck/tests/native-profiles.py > /work/output/native-profiles-summary.json
# Repair cannot rely on a clean OBS profile: restore a muted, zero-gain input
# whose output tracks were disabled and monitoring was accidentally enabled.
python3 /src/steamdeck/tests/native-audio.py seed >/work/output/audio-stale-state-seeded.json

ffmpeg -hide_banner -listen 1 -i rtmp://127.0.0.1:1935/live/fixture-key -c copy -y /work/output/received.flv >/work/rtmp.log 2>&1 &
receiver=$!
pw-dump >/work/output/nodes-before-stream.json
/src/dist/obsgod deck start > /work/output/start.json
python3 /src/steamdeck/tests/native-audio.py snapshot obsgod_game.monitor >/work/output/audio-route-stream.json
/src/dist/obsgod deck start > /work/output/start-again.json
python3 /src/steamdeck/tests/native-media.py --stream-active > /work/output/native-live-media-summary.json
OBSGOD_DISPOSABLE_AUDIO_FIXTURE=1 python3 /src/steamdeck/tests/native-resilience.py --game-pid "$game_audio_pid" > /work/output/audio-hotplug.json
sleep 4
/src/dist/obsgod deck status > /work/output/status-live.json
/src/dist/obsgod deck stop > /work/output/stop.json
/src/dist/obsgod deck stop > /work/output/stop-again.json
wait "$receiver" || true
ffprobe -v error -show_streams -show_format -of json /work/output/received.flv > /work/output/stream-probe.json
ffmpeg -v error -ss 2 -i /work/output/received.flv -frames:v 1 -f rawvideo -pix_fmt rgb24 -y /work/output/stream-frame.rgb
ffmpeg -hide_banner -i /work/output/received.flv -af volumedetect -vn -f null - >/work/output/stream-audio.txt 2>&1
ffmpeg -v error -ss 1 -i /work/output/received.flv -t 2 -vn -ar 48000 -ac 1 -c:a pcm_s16le -y /work/output/stream-audio.wav
python3 /src/steamdeck/tests/native-audio.py measure /work/output/stream-audio.wav 440 >/work/output/stream-audio-metrics.json

stream_audio_route() {
  local route_name=$1 route_monitor=$2 route_frequency=$3
  ffmpeg -hide_banner -listen 1 -i rtmp://127.0.0.1:1935/live/fixture-key -c copy -y "/work/output/$route_name.flv" >"/work/$route_name-receiver.log" 2>&1 &
  local route_receiver=$!
  /src/dist/obsgod deck start >"/work/output/$route_name-start.json"
  python3 /src/steamdeck/tests/native-audio.py snapshot "$route_monitor" >"/work/output/$route_name-route.json"
  sleep 3
  /src/dist/obsgod deck stop >"/work/output/$route_name-stop.json"
  wait "$route_receiver" || true
  ffmpeg -v error -ss 1 -i "/work/output/$route_name.flv" -t 2 -vn -ar 48000 -ac 1 -c:a pcm_s16le -y "/work/output/$route_name.wav"
  python3 /src/steamdeck/tests/native-audio.py measure "/work/output/$route_name.wav" "$route_frequency" >"/work/output/$route_name-audio-metrics.json"
}

# Once the owned game exits, discover the real default output rather than
# caching the old game's monitor. This is a new-start route test, not live
# hotplug-following or real SteamOS audio qualification.
kill "$game_audio_pid"
wait "$game_audio_pid" || true
wait_for_fixture_service PulseAudio "$pulse_pid" /work/pulse.log audio_input_absent "$game_audio_pid"
stream_audio_route audio-default-fallback obsgod_decoy.monitor 880

# Change the default device between starts and verify a fresh monitor choice.
gst-launch-1.0 -q audiotestsrc is-live=true wave=sine freq=440 volume=0.2 ! audioconvert ! pulsesink device=obsgod_game >/work/new-default-audio-producer.log 2>&1 &
new_default_audio_pid=$!
wait_for_fixture_service NewDefaultTone "$new_default_audio_pid" /work/new-default-audio-producer.log audio_input_present "$new_default_audio_pid"
pactl set-default-sink obsgod_game
stream_audio_route audio-default-changed obsgod_game.monitor 440
# Failed start must stop its pending output and must not auto-start later when
# a server appears. No external provider or actual stream key is involved.
if /src/dist/obsgod deck start >/work/output/start-failure.json 2>/work/output/start-failure.stderr; then
  echo 'Expected a failed start with no RTMP receiver' >&2; exit 1
fi
/src/dist/obsgod deck status >/work/output/status-after-failure.json
python3 - <<'PY'
import json,socket
s=socket.socket();s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',1935));s.listen(1);s.settimeout(6)
connected=False
try:
 c,_=s.accept();connected=True;c.close()
except TimeoutError: pass
finally:s.close()
json.dump({'unexpected_connection':connected},open('/work/output/no-late-start.json','w'))
assert not connected,'OBS attempted an unexpected late stream connection'
PY
/src/dist/obsgod deck restart > /work/output/restart.json
# Qualify the new local credential controls only after the preceding real OBS
# lifecycle has positively closed the managed instance. This helper uses the
# newly packaged candidate binary and never exports passwords or starts output.
python3 /src/steamdeck/tests/native-control-password.py
python3 - <<'PY'
import json
from pathlib import Path
p=Path('/work/output')
for name in ['configure','test-recording','start','start-again','status-live','stop','stop-again','restart']:
 r=json.loads((p/(name+'.json')).read_text());assert r['ok'],(name,r)
for name in ['start','start-again','status-live']:
 r=json.loads((p/(name+'.json')).read_text());assert r['stream']['active'] and r['stream']['bytes']>0
for name in ['stop','stop-again']:
 assert not json.loads((p/(name+'.json')).read_text())['stream']['active']
clip=json.loads((p/'test-recording.json').read_text())
assert clip['recording'] is False and clip['runtime']['recording'] is False,'clip completion preceded confirmed recording stop'
restart=json.loads((p/'restart.json').read_text())
assert restart['process']=='absent' and restart['output_known'] is True,'managed OBS shutdown was not confirmed'
control=json.loads((p/'control-password-qualification.json').read_text())
assert control['status']=='passed' and control['ordinary_obs_preserved'] and control['secret_values_exported'] is False
assert [case['mode'] for case in control['cases']]==['generated','manual']
assert all(case['actual_obs_new_password_authenticated'] and case['old_password_rejected_code']==4009 and case['output_stayed_stopped'] and case['final_managed_shutdown_confirmed'] for case in control['cases'])
workflow=control['cases'][0]['settings_only_workflow']
assert workflow['status']=='passed' and workflow['all_output_remained_inactive'] and workflow['managed_settings_and_credentials_preserved'] and workflow['private_generic_configuration_removed']
ordinary=Path('/work/home/.var/app/com.obsproject.Studio/config/obs-studio')
assert sorted(f.name for f in ordinary.iterdir())==['preserve.txt'],'ordinary OBS configuration was used'
assert (ordinary/'preserve.txt').read_text()=='ordinary OBS configuration must remain unchanged\n'
for name in ['recording-probe','stream-probe']:
 r=json.loads((p/(name+'.json')).read_text());streams=r['streams']
 video=next(s for s in streams if s['codec_type']=='video');audio=next(s for s in streams if s['codec_type']=='audio')
 assert video['codec_name']=='h264' and video['width']==1280 and video['height']==720
 assert audio['codec_name']=='aac'
pixels=(p/'frame.rgb').read_bytes();assert max(pixels)>32 and max(pixels)-min(pixels)>16,'recorded output is blank'
pixels=(p/'stream-frame.rgb').read_bytes();assert max(pixels)>32 and max(pixels)-min(pixels)>16,'streamed output is blank'
hashes=[line.split(',')[-1].strip() for line in (p/'frames.md5').read_text().splitlines() if not line.startswith('#')]
assert len(hashes)==3 and len(set(hashes))>1,'video frames do not move'
for name in ['recording-audio','stream-audio','audio-default-fallback-audio','audio-default-changed-audio']:
 metrics=json.loads((p/(name+'-metrics.json')).read_text())
 assert metrics['status']=='passed' and metrics['audible'] and metrics['expected_tone'],(name,metrics)
 assert metrics['rms_dbfs']>-40 and metrics['peak_dbfs']>-35,(name,metrics)
assert json.loads((p/'silence-negative-control.json').read_text())['status']=='silence-rejected-as-expected'
assert not json.loads((p/'start-failure.json').read_text())['ok']
assert not json.loads((p/'status-after-failure.json').read_text())['stream']['active']
for name in ['configure','test-recording','start','status-live','stop']:
 assert 'fixture-key' not in (p/(name+'.json')).read_text(),name
print('PASS: real OBS / GStreamer / synthetic PipeWire / PulseAudio: measured recording+RTMP game tone over default decoy, stale mixer repair, game-exit default fallback, changed default on next start, silence negative control, moving video, repeated lifecycle, failed-start cleanup, no late connection, generated/manual local control password recovery and old-password rejection. Real Flatpak audio mapping, SteamOS hardware and external providers remain untested.')
PY
