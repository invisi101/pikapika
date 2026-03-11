#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_DIR="$HOME/.local/share/pikapika"
BIN_DIR="$HOME/.local/bin"

# Install dependencies
echo "Installing dependencies..."
if command -v pacman &>/dev/null; then
    sudo pacman -S --needed --noconfirm python-gobject libadwaita mat2 perl-image-exiftool
elif command -v apt-get &>/dev/null; then
    sudo apt-get install -y python3-gi libadwaita-1-0 gir1.2-adw-1 mat2 libimage-exiftool-perl
elif command -v dnf &>/dev/null; then
    sudo dnf install -y python3-gobject libadwaita mat2 perl-Image-ExifTool
else
    echo "Warning: Could not detect package manager. Please install manually:"
    echo "  python-gobject, libadwaita, mat2, exiftool"
fi

# Install app to ~/.local/share/pikapika/
mkdir -p "$APP_DIR/assets"
cp "$SCRIPT_DIR/pikapika.py" "$APP_DIR/"
cp "$SCRIPT_DIR/assets/VeganStyle.ttf" "$APP_DIR/assets/"
cp "$SCRIPT_DIR/assets/pikapika.svg" "$APP_DIR/assets/"
chmod +x "$APP_DIR/pikapika.py"
echo "App installed to $APP_DIR"

# Install launcher to ~/.local/bin/
mkdir -p "$BIN_DIR"
ln -sf "$APP_DIR/pikapika.py" "$BIN_DIR/pikapika"
echo "Launcher symlink created at $BIN_DIR/pikapika"

# Install font
FONT_DIR="$HOME/.local/share/fonts"
mkdir -p "$FONT_DIR"
cp "$APP_DIR/assets/VeganStyle.ttf" "$FONT_DIR/"
fc-cache -f 2>/dev/null || true
echo "Font installed to $FONT_DIR"

# Install icon
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$ICON_DIR"
cp "$APP_DIR/assets/pikapika.svg" "$ICON_DIR/"
echo "Icon installed to $ICON_DIR"

# Install desktop entry
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
sed -e "s|PIKAPIKA_PATH|$APP_DIR|g" -e 's|^Icon=.*|Icon=pikapika|' "$SCRIPT_DIR/pikapika.desktop" > "$DESKTOP_DIR/pikapika.desktop"
echo "Desktop entry installed to $DESKTOP_DIR"

echo "Pikapika installed successfully."
echo "You can now run 'pikapika' from the terminal or launch it from your app menu."
