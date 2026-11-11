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
pipewire >/work/pipewire.log 2>&1 &
wireplumber >/work/wireplumber.log 2>&1 &
pulseaudio --daemonize=no --exit-idle-time=-1 >/work/pulse.log 2>&1 &
for attempt in {1..50}; do
  if pw-dump >/dev/null 2>&1 && pactl info >/dev/null 2>&1; then break; fi
  sleep .2
done
pactl load-module module-null-sink sink_name=obsgod_test >/dev/null
pactl set-default-sink obsgod_test
(
  while true; do
    # GStreamer 1.26's synthetic PipeWire sink can fault on consumer teardown.
    # Disable its debugger spin so this disposable fixture actually exits and
    # the supervisor can restart it. Gamescope itself is not this gst process.
    gst-launch-1.0 --no-fault -q videotestsrc is-live=true pattern=ball ! video/x-raw,width=1280,height=800,framerate=30/1 ! pipewiresink mode=provide 'stream-properties=props,node.name=gamescope,media.class=Video/Source' >>/work/video-producer.log 2>&1 || true
    sleep .2
  done
) &
gst-launch-1.0 -q audiotestsrc is-live=true wave=sine ! audioconvert ! pulsesink device=obsgod_test >/work/audio-producer.log 2>&1 &

# Replace only the Flatpak invocation in this disposable container. Capture,
# PulseAudio, encoding, OBS and authenticated WebSocket traffic remain real.
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
os.execvp('obs',['obs']+args[index+1:])
PY
chmod 700 /work/bin/flatpak

# Build upstream's exact Flathub source revision, kept outside the product.
mkdir -p /work/plugin-src
tar xf /work/gstreamer-source.tar.gz -C /work/plugin-src --strip-components=1
printf '%s\n' 'const char *obs_gstreamer_version = "v0.4.1-smoke";' > /work/plugin-src/version.c
plugin="$HOME/.var/app/com.obsproject.Studio/config/obsgod/obs-studio/plugins/obs-gstreamer/bin/64bit"
mkdir -p "$plugin"
gcc -shared -fPIC -O2 -o "$plugin/obs-gstreamer.so" /work/plugin-src/gstreamer*.c /work/plugin-src/version.c $(pkg-config --cflags --libs libobs gstreamer-app-1.0 gstreamer-audio-1.0 gstreamer-video-1.0 gstreamer-net-1.0)
printf '%s\n' '{"version":1,"server":"rtmp://127.0.0.1:1935/live","stream_key":"fixture-key","bitrate":3000,"fps":30,"encoder":"x264","microphone":false}' | /src/dist/obsgod deck configure > /work/output/configure.json
pw-dump > /work/output/pipewire-nodes.json
/src/dist/obsgod deck test-recording > /work/output/test-recording.json
clip=$(python3 -c 'import json;print(json.load(open("/work/output/test-recording.json"))["recording_path"])')
ffprobe -v error -show_streams -show_format -of json "$clip" > /work/output/recording-probe.json
ffmpeg -v error -ss 2 -i "$clip" -frames:v 1 -y /work/output/capture.png
ffmpeg -v error -ss 2 -i "$clip" -frames:v 1 -f rawvideo -pix_fmt rgb24 -y /work/output/frame.rgb
ffmpeg -v error -ss 1 -i "$clip" -an -vf fps=1 -frames:v 3 -f framemd5 -y /work/output/frames.md5
ffmpeg -hide_banner -i "$clip" -af volumedetect -vn -f null - >/work/output/recording-audio.txt 2>&1

ffmpeg -hide_banner -listen 1 -i rtmp://127.0.0.1:1935/live/fixture-key -c copy -y /work/output/received.flv >/work/rtmp.log 2>&1 &
receiver=$!
pw-dump >/work/output/nodes-before-stream.json
/src/dist/obsgod deck start > /work/output/start.json
/src/dist/obsgod deck start > /work/output/start-again.json
sleep 4
/src/dist/obsgod deck status > /work/output/status-live.json
/src/dist/obsgod deck stop > /work/output/stop.json
/src/dist/obsgod deck stop > /work/output/stop-again.json
wait "$receiver" || true
ffprobe -v error -show_streams -show_format -of json /work/output/received.flv > /work/output/stream-probe.json
ffmpeg -v error -ss 2 -i /work/output/received.flv -frames:v 1 -f rawvideo -pix_fmt rgb24 -y /work/output/stream-frame.rgb
ffmpeg -hide_banner -i /work/output/received.flv -af volumedetect -vn -f null - >/work/output/stream-audio.txt 2>&1
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
python3 - <<'PY'
import json,re
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
for name in ['recording-probe','stream-probe']:
 r=json.loads((p/(name+'.json')).read_text());streams=r['streams']
 video=next(s for s in streams if s['codec_type']=='video');audio=next(s for s in streams if s['codec_type']=='audio')
 assert video['codec_name']=='h264' and video['width']==1280 and video['height']==720
 assert audio['codec_name']=='aac'
pixels=(p/'frame.rgb').read_bytes();assert max(pixels)>32 and max(pixels)-min(pixels)>16,'recorded output is blank'
pixels=(p/'stream-frame.rgb').read_bytes();assert max(pixels)>32 and max(pixels)-min(pixels)>16,'streamed output is blank'
hashes=[line.split(',')[-1].strip() for line in (p/'frames.md5').read_text().splitlines() if not line.startswith('#')]
assert len(hashes)==3 and len(set(hashes))>1,'video frames do not move'
audio=(p/'recording-audio.txt').read_text();assert re.search(r'max_volume: -?[0-9.]+ dB',audio),audio
audio=(p/'stream-audio.txt').read_text();assert re.search(r'max_volume: -?[0-9.]+ dB',audio),audio
assert not json.loads((p/'start-failure.json').read_text())['ok']
assert not json.loads((p/'status-after-failure.json').read_text())['stream']['active']
for name in ['configure','test-recording','start','status-live','stop']:
 assert 'fixture-key' not in (p/(name+'.json')).read_text(),name
print('PASS: real OBS / GStreamer / synthetic PipeWire / PulseAudio / moving recording / nonblank local RTMP / repeated lifecycle / failed-start cleanup / no late connection. Hardware and Kick untested.')
PY
