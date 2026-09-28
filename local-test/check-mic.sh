#!/bin/bash
# Vérifie ce que le micro configuré dans config.yaml capte réellement.
# Enregistre 10 s (en parallèle de BirdNET-Go, sans l'arrêter) et donne un diagnostic.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEV="${1:-$(sed -n 's/^ *device: "\(.*\)"$/\1/p' "$HERE/config.yaml" | head -1)}"   # ou : ./check-mic.sh "Nom du micro"
[ -n "$DEV" ] || { echo "Aucun device entre guillemets dans config.yaml"; exit 1; }
TMP=$(mktemp -d)
trap 'rm -rf "$TMP"' EXIT

echo "Micro : $DEV"
if [ -x "$HERE/tools/mic-status" ] && PID=$(cat "$HERE/birdnet-go.pid" 2>/dev/null) && kill -0 "$PID" 2>/dev/null; then
  USED=$("$HERE/tools/mic-status" "$PID" | paste -sd ',' -)
  echo "BirdNET-Go capte actuellement : ${USED:-rien}"
  [ "$USED" != "$DEV" ] && echo "⚠️  Ce n'est pas le micro de config.yaml : ./stop.sh && ./start.sh (ou attendre la surveillance)."
fi

# Gain matériel exposé à macOS (commande USB du micro).
cat > "$TMP/gain.swift" <<'EOF'
import CoreAudio
let target = CommandLine.arguments[1]
var a = AudioObjectPropertyAddress(mSelector: kAudioHardwarePropertyDevices, mScope: kAudioObjectPropertyScopeGlobal, mElement: 0)
var sz: UInt32 = 0
AudioObjectGetPropertyDataSize(AudioObjectID(kAudioObjectSystemObject), &a, 0, nil, &sz)
var ids = [AudioObjectID](repeating: 0, count: Int(sz) / 4)
AudioObjectGetPropertyData(AudioObjectID(kAudioObjectSystemObject), &a, 0, nil, &sz, &ids)
for id in ids {
  var name: Unmanaged<CFString>?
  var n = AudioObjectPropertyAddress(mSelector: kAudioObjectPropertyName, mScope: kAudioObjectPropertyScopeGlobal, mElement: 0)
  var ns = UInt32(MemoryLayout<Unmanaged<CFString>?>.size)
  AudioObjectGetPropertyData(id, &n, 0, nil, &ns, &name)
  guard let s = name?.takeRetainedValue() as String?, s == target else { continue }
  var db: Float32 = 0, r = AudioValueRange()
  var p = AudioObjectPropertyAddress(mSelector: kAudioDevicePropertyVolumeDecibels, mScope: kAudioDevicePropertyScopeInput, mElement: 1)
  var sd = UInt32(MemoryLayout<Float32>.size)
  guard AudioObjectGetPropertyData(id, &p, 0, nil, &sd, &db) == 0 else { print("Gain macOS : non exposé"); exit(0) }
  p.mSelector = kAudioDevicePropertyVolumeRangeDecibels
  var sr = UInt32(MemoryLayout<AudioValueRange>.size)
  AudioObjectGetPropertyData(id, &p, 0, nil, &sr, &r)
  print(String(format: "Gain macOS : %+.1f dB (plage %+.1f à %+.1f dB)", db, r.mMinimum, r.mMaximum))
}
EOF
swift "$TMP/gain.swift" "$DEV" 2>/dev/null || echo "Gain macOS : lecture impossible"

echo "Enregistrement de 10 s... (fais un bruit près du micro : claquement de doigts, sifflement)"
ffmpeg -hide_banner -loglevel error -f avfoundation -i ":$DEV" -t 10 -ac 2 -ar 48000 \
  -c:a pcm_s16le -y "$TMP/rec.wav"

stat() { sox "$1" -n stats 2>&1 | awk -v k="$2" '$0 ~ "^"k {print $4}'; }  # 1re valeur = « Overall » (ou mono)
PK=$(stat "$TMP/rec.wav" "Pk lev dB")
RMS=$(stat "$TMP/rec.wav" "RMS lev dB")
sox "$TMP/rec.wav" "$TMP/diff.wav" remix 1,2v-1
DIFF=$(stat "$TMP/diff.wav" "RMS lev dB")   # G − D
echo "Crête : $PK dBFS   Niveau moyen (RMS) : $RMS dBFS"

if [ "$PK" = "-inf" ]; then
  echo "❌ SILENCE TOTAL : le micro est coupé (tap-to-mute : touche le dessus du micro) ou débranché."
  exit 1
fi
awk -v p="$PK" 'BEGIN { exit !(p > -1) }' && echo "⚠️  Saturation : baisse le gain (molette du micro), sauf si c'était un choc sur le micro."
awk -v r="$RMS" 'BEGIN { exit !(r < -70) }' && echo "⚠️  Niveau très faible : monte le gain si les chants lointains ne sont pas détectés."
# Mono : G et D quasi identiques (différence 20 dB sous le signal). Stéréo : capsules distinctes.
if [ "$DIFF" = "-inf" ] || awk -v d="$DIFF" -v r="$RMS" 'BEGIN { exit !(d < r - 20) }'; then
  echo "Canaux G/D quasi identiques → directivité mono (cardioïde, omni ou bidirectionnelle) : vérifie sur le micro que c'est omni."
else
  echo "Canaux G/D différents → directivité stéréo."
fi
echo "✅ Le micro capte du son."
