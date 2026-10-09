#!/usr/bin/env bash
# Compila el APK sin Gradle (aapt2 + javac + d8 + apksigner). Uso: bash android/build.sh [carpeta_salida]
# Requiere Android Studio (JBR) y el SDK en %LOCALAPPDATA%/Android/Sdk. La llave (keystore) NO va en el repo.
set -euo pipefail
cd "$(dirname "$0")"
SDK="${ANDROID_SDK_ROOT:-$LOCALAPPDATA/Android/Sdk}"
BT="$(ls -d "$SDK"/build-tools/* | sort -V | tail -1)"
JAR="$(ls -d "$SDK"/platforms/android-* | sort -V | tail -1)/android.jar"
JBR="C:/Program Files/Android/Android Studio/jbr/bin"
export JAVA_HOME="C:/Program Files/Android/Android Studio/jbr"; export PATH="$JBR:$PATH"
OUT="${1:-../../apk}"; mkdir -p "$OUT"; OUT="$(cd "$OUT" && pwd)"
KS="$OUT/ede-puerta.keystore"
W="$(mktemp -d)"
if [ ! -f "$KS" ]; then
  PASS="$(head -c 48 /dev/urandom | base64 | tr -dc 'A-Za-z0-9' | head -c 20)"
  "$JBR/keytool.exe" -genkeypair -keystore "$KS" -alias ede -keyalg RSA -keysize 2048 -validity 10000 \
     -storepass "$PASS" -keypass "$PASS" -dname "CN=EDE Puerta, O=Hilario GRP, C=PE"
  echo "$PASS" > "$OUT/keystore-password.txt"
  echo "Llave nueva creada en $KS (clave en keystore-password.txt). GUARDALA: sin ella no podras actualizar la app."
fi
PASS="$(cat "$OUT/keystore-password.txt")"
"$BT/aapt2.exe" compile --dir res -o "$W/res.zip"
"$BT/aapt2.exe" link -o "$W/base.apk" -I "$JAR" --manifest AndroidManifest.xml --min-sdk-version 24 \
   --target-sdk-version 34 --version-code 1 --version-name 1.0 --java "$W/gen" "$W/res.zip"
mkdir -p "$W/classes"
"$JBR/javac.exe" --release 8 -Xlint:-options -cp "$JAR" -d "$W/classes" $(find src "$W/gen" -name '*.java')
"$BT/d8.bat" --release --min-api 24 --lib "$JAR" --output "$W" $(find "$W/classes" -name '*.class')
( cd "$W" && "$JBR/jar.exe" -uf base.apk classes.dex )
"$BT/zipalign.exe" -f -p 4 "$W/base.apk" "$W/aligned.apk"
"$BT/apksigner.bat" sign --ks "$KS" --ks-pass "pass:$PASS" --out "$OUT/EDE-Puerta.apk" "$W/aligned.apk"
"$BT/apksigner.bat" verify --verbose "$OUT/EDE-Puerta.apk" | head -5
ls -l "$OUT/EDE-Puerta.apk"
