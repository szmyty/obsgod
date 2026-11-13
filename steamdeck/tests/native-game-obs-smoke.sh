#!/usr/bin/env bash
# Actual OBS output/controller integration with synthetic Gamescope/game facts.
# Requires disposable /work, read-only /src, candidate dist/obsgod + capture lib,
# and /work/gstreamer-source.tar.gz. Never mount user data here.
set -euo pipefail
ulimit -c 0
test -f /.dockerenv || { echo 'Run only in the disposable native test container.' >&2; exit 2; }
test -x /src/dist/obsgod
test -f /src/dist/libgstobsgodcapture.so
rm -rf /work/home /work/runtime /work/output /work/plugin-src
export HOME=/work/home XDG_CONFIG_HOME=/work/home/.config XDG_RUNTIME_DIR=/work/runtime
export DISPLAY=:99 LIBGL_ALWAYS_SOFTWARE=1 QT_X11_NO_MITSHM=1
export PATH=/work/bin:$PATH
umask 077
mkdir -p "$HOME" "$XDG_RUNTIME_DIR" /work/bin /work/output
chmod 700 "$XDG_RUNTIME_DIR"
cleanup() { jobs -pr | xargs -r kill 2>/dev/null || true; }
trap cleanup EXIT
Xvfb :99 -screen 0 1280x800x24 -ac >/work/xvfb.log 2>&1 &
pipewire >/work/pipewire.log 2>&1 &
pipewire_pid=$!
for n in {1..50}; do
  if timeout 1 pw-dump >/work/output/pipewire-ready.json 2>/dev/null; then break; fi
  kill -0 "$pipewire_pid"
  sleep .1
done
timeout 1 pw-dump >/work/output/pipewire-ready.json
wireplumber >/work/wireplumber.log 2>&1 &
wireplumber_pid=$!
for n in {1..50}; do
  timeout 1 pw-dump >/work/output/wireplumber-ready.json
  if python3 - "$wireplumber_pid" /work/output/wireplumber-ready.json <<'PY'
import json,sys
nodes=json.load(open(sys.argv[2]))
raise SystemExit(0 if any(str((x.get('info')or{}).get('props',{}).get('application.process.id'))==sys.argv[1] for x in nodes) else 1)
PY
  then break; fi
  kill -0 "$wireplumber_pid"
  sleep .1
done
pulseaudio --daemonize=no --exit-idle-time=-1 >/work/pulse.log 2>&1 &
pulse_pid=$!
for n in {1..50}; do
  if timeout 1 pactl info >/dev/null 2>&1; then break; fi
  kill -0 "$pulse_pid"
  sleep .1
done
timeout 1 pactl info >/dev/null
pactl load-module module-null-sink sink_name=obsgod_scene_audio >/dev/null
pactl set-default-sink obsgod_scene_audio
gst-launch-1.0 --no-fault -q audiotestsrc is-live=true wave=sine freq=440 volume=.3 ! audioconvert ! pulsesink device=obsgod_scene_audio >/work/audio-producer.log 2>&1 &

cat > /work/bin/flatpak <<'PY'
#!/usr/bin/env python3
import os,sys
args=sys.argv[1:]
if args[0]=='info':raise SystemExit(0)
if args[0]!='run':raise SystemExit(2)
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
printf '%s\n' 'ordinary OBS scene/setting marker' > "$ordinary/preserve.txt"
printf '%s  %s\n' '566d547e83140d53a0aa22ed152cebc436725b47e4ead452e79cf250da531268' /work/gstreamer-source.tar.gz | sha256sum --check -
mkdir -p /work/plugin-src
tar xf /work/gstreamer-source.tar.gz -C /work/plugin-src --strip-components=1
printf '%s\n' 'const char *obs_gstreamer_version = "v0.4.1-game-smoke";' > /work/plugin-src/version.c
plugin="$HOME/.var/app/com.obsproject.Studio/config/obsgod/obs-studio/plugins/obs-gstreamer/bin/64bit"
mkdir -p "$plugin"
gcc -shared -fPIC -O2 -o "$plugin/obs-gstreamer.so" /work/plugin-src/gstreamer*.c /work/plugin-src/version.c $(pkg-config --cflags --libs libobs gstreamer-app-1.0 gstreamer-audio-1.0 gstreamer-video-1.0 gstreamer-net-1.0)
gcc -O2 -Wall -Wextra -Werror -o /work/capture-fixture /src/steamdeck/tests/capture-fixture.c $(pkg-config --cflags --libs libpipewire-0.3)
python3 /src/steamdeck/tests/native-game-obs.py

# Inspect real viewer-received H264/AAC at each held scene phase, not just OBS
# screenshots or source registration. The same known tone must survive scenes.
python3 - <<'PY'
import importlib.util,json,os,pathlib,subprocess,hashlib
p=pathlib.Path('/work/output')
spec=importlib.util.spec_from_file_location('native_game_obs','/src/steamdeck/tests/native-game-obs.py')
game=importlib.util.module_from_spec(spec);spec.loader.exec_module(game)
q=json.loads((p/'game-obs-qualification.json').read_text())
phases=list(q['phases'].items())+[('black-fallback',q['black_fallback'])]
media={}
last_duration=-1
for name,phase in phases:
 source=p/('black-fallback.flv' if name=='black-fallback' else 'transitions.flv')
 assert phase['end_ms']>phase['at_ms']+2000,(name,phase)
 if name!='black-fallback':
  assert phase['at_ms']>last_duration,(name,'output duration restarted')
  last_duration=phase['end_ms']
 at=(phase['at_ms']+phase['end_ms'])/2000
 raw=p/(name+'-viewer.rgb')
 subprocess.run(['ffmpeg','-v','error','-ss',str(at),'-i',str(source),'-frames:v','1','-vf','scale=160:90','-f','rawvideo','-pix_fmt','rgb24','-y',str(raw)],check=True)
 pixels=game.rgb_kind(raw.read_bytes(),phase['pixels']['expected'])
 wave=p/(name+'-audio.wav')
 subprocess.run(['ffmpeg','-v','error','-ss',str(at),'-i',str(source),'-t','1','-vn','-ac','1','-ar','48000','-c:a','pcm_s16le','-y',str(wave)],check=True)
 audio=json.loads(subprocess.check_output(['python3','/src/steamdeck/tests/native-audio.py','measure',str(wave),'440'],text=True))
 media[name]={'viewer_pixels':pixels,'viewer_audio':audio,'sample_at_seconds':at}
clip=json.loads((p/'local-clip.json').read_text())
clip_path=clip['recording_path']
probe=json.loads(subprocess.check_output(['ffprobe','-v','error','-show_streams','-show_format','-of','json',clip_path],text=True))
assert float(probe['format']['duration'])>=9.5,probe
subprocess.run(['ffmpeg','-v','error','-ss','1','-i',clip_path,'-t','1','-vn','-ac','1','-ar','48000','-c:a','pcm_s16le','-y',str(p/'clip-audio.wav')],check=True)
media['local-clip-audio']=json.loads(subprocess.check_output(['python3','/src/steamdeck/tests/native-audio.py','measure',str(p/'clip-audio.wav'),'440'],text=True))
ordinary=pathlib.Path('/work/home/.var/app/com.obsproject.Studio/config/obs-studio')
assert [x.name for x in ordinary.iterdir()]==['preserve.txt']
assert (ordinary/'preserve.txt').read_text()=='ordinary OBS scene/setting marker\n'
q['decoded_media']=media
q['ordinary_obs']='unchanged'
q['source_revision']=os.environ.get('OBSGOD_QUALIFIED_REVISION','unrecorded development run')
q['binary_sha256']=hashlib.sha256(pathlib.Path('/src/dist/obsgod').read_bytes()).hexdigest()
q['capture_library_sha256']=hashlib.sha256(pathlib.Path('/src/dist/libgstobsgodcapture.so').read_bytes()).hexdigest()
(p/'game-obs-qualification.json').write_text(json.dumps(q,indent=2)+'\n')
print('PASS: actual OBS game/idle/game/unsupported/black scenes and advancing local RTMP; decoded scene pixels and440Hz audible at every phase; local10sclip; no implicit output restart; legacy sources hidden; ordinary OBS preserved. Synthetic game producer, not Steam Deck qualification.')
PY

# Rich idle media uses the same still-live disposable display/audio session.
python3 /src/steamdeck/tests/native-idle-media.py
