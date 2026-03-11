#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

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

# Install VeganStyle font to user fonts
FONT_DIR="$HOME/.local/share/fonts"
mkdir -p "$FONT_DIR"
cp "$SCRIPT_DIR/assets/VeganStyle.ttf" "$FONT_DIR/"
fc-cache -f 2>/dev/null || true
echo "Font installed to $FONT_DIR"

# Install icon
ICON_DIR="$HOME/.local/share/icons/hicolor/scalable/apps"
mkdir -p "$ICON_DIR"
cp "$SCRIPT_DIR/assets/pikapika.svg" "$ICON_DIR/"
echo "Icon installed to $ICON_DIR"

# Install desktop entry (patch icon path to use system icon name)
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
sed 's|^Icon=.*|Icon=pikapika|' "$SCRIPT_DIR/pikapika.desktop" > "$DESKTOP_DIR/pikapika.desktop"
echo "Desktop entry installed to $DESKTOP_DIR"

echo "Pikapika installed successfully."
