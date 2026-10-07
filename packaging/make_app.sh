#!/bin/bash
# Wrap the PyInstaller executable in Toploader.app (runs on macOS, after the build).
#   packaging/make_app.sh dist/toploader OUT_DIR   ->  OUT_DIR/Toploader.app
#
# Toploader is a terminal app, so the .app is a small launcher: double-clicking
# it opens the bundled executable in a new terminal window, preferring one that
# shows images (Ghostty, kitty, WezTerm) and otherwise whatever opens Unix
# executables (Terminal unless changed). The executable itself is
# Contents/MacOS/toploader-cli, which can also be linked onto the PATH.
set -euo pipefail

cli="$1"
out="$2"
here="$(cd "$(dirname "$0")" && pwd)"
version="$(python -c 'import toploader; print(toploader.__version__)')"
app="$out/Toploader.app"

rm -rf "$app"
mkdir -p "$app/Contents/MacOS" "$app/Contents/Resources"
cp "$cli" "$app/Contents/MacOS/toploader-cli"
python "$here/make_icon.py" "$app/Contents/Resources/Toploader.icns"

cat > "$app/Contents/MacOS/Toploader" <<'SH'
#!/bin/bash
# Open Toploader in a new terminal window, in one that shows card images if installed.
cli="$(cd "$(dirname "$0")" && pwd)/toploader-cli"
has() { [[ -d "/Applications/$1.app" || -d "$HOME/Applications/$1.app" ]]; }
if has Ghostty; then exec open -na Ghostty --args -e "$cli"
elif has kitty; then exec open -na kitty --args "$cli"
elif has WezTerm; then exec open -na WezTerm --args start -- "$cli"
else exec open "$cli"
fi
SH
chmod +x "$app/Contents/MacOS/Toploader" "$app/Contents/MacOS/toploader-cli"

cat > "$app/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Toploader</string>
  <key>CFBundleDisplayName</key><string>Toploader</string>
  <key>CFBundleIdentifier</key><string>io.github.stemerlini.toploader</string>
  <key>CFBundleVersion</key><string>$version</string>
  <key>CFBundleShortVersionString</key><string>$version</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>CFBundleExecutable</key><string>Toploader</string>
  <key>CFBundleIconFile</key><string>Toploader</string>
  <key>LSApplicationCategoryType</key><string>public.app-category.utilities</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHumanReadableCopyright</key><string>Fan project, not affiliated with Nintendo or The Pokémon Company.</string>
</dict>
</plist>
PLIST

# Ad-hoc signature: not notarised, but keeps the bundle consistent for Gatekeeper.
if command -v codesign >/dev/null; then
  codesign --force --sign - "$app/Contents/MacOS/toploader-cli"
  codesign --force --sign - "$app"
fi
echo "$app"
