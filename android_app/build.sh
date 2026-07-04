#!/bin/bash
# Build route-no-traffic.apk without Gradle/Android Studio, using the
# Debian-packaged Android tools: aapt, dalvik-exchange (dx), zipalign,
# apksigner, plus android.jar from android-sdk-platform-23.
set -euo pipefail
cd "$(dirname "$0")"

# Compile/link against an API-34 framework stub (Robolectric's android-all,
# which bundles resources.arsc) so newer symbols like PictureInPictureParams
# and AudioFocusRequest resolve. Auto-downloaded once if missing.
ANDROID_JAR=android-all-34.jar
ANDROID_JAR_URL="https://repo1.maven.org/maven2/org/robolectric/android-all/14-robolectric-10818077/android-all-14-robolectric-10818077.jar"
OUT=build

if [ ! -f "$ANDROID_JAR" ]; then
    echo "==> fetching framework stub ($ANDROID_JAR)"
    curl -sSL -o "$ANDROID_JAR" "$ANDROID_JAR_URL"
fi

rm -rf "$OUT" && mkdir -p "$OUT/obj"

echo "==> 1/6 icon"
python3 make_icon.py

echo "==> 2/6 javac"
javac --release 8 -classpath "$ANDROID_JAR" -d "$OUT/obj" \
    src/app/route/notraffic/*.java

echo "==> 3/6 dex"
dalvik-exchange --dex --output="$OUT/classes.dex" "$OUT/obj"

echo "==> 4/6 aapt package (manifest + resources + assets)"
aapt package -f \
    -M AndroidManifest.xml \
    -S res \
    -A assets \
    -I "$ANDROID_JAR" \
    -F "$OUT/app.unsigned.apk"
(cd "$OUT" && aapt add app.unsigned.apk classes.dex)

echo "==> 5/6 zipalign"
zipalign -f 4 "$OUT/app.unsigned.apk" "$OUT/app.aligned.apk"

echo "==> 6/6 sign"
if [ ! -f "./debug.keystore" ]; then
    keytool -genkeypair -keystore "./debug.keystore" \
        -storepass android -keypass android -alias appkey \
        -keyalg RSA -keysize 2048 -validity 10000 \
        -dname "CN=Route NoTraffic, O=Dev, C=GR"
fi
apksigner sign --ks "./debug.keystore" \
    --ks-pass pass:android --key-pass pass:android \
    --out "$OUT/route-no-traffic.apk" "$OUT/app.aligned.apk"
apksigner verify --verbose "$OUT/route-no-traffic.apk" | head -5

ls -la "$OUT/route-no-traffic.apk"
echo "DONE: $OUT/route-no-traffic.apk"
