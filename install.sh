#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"

# Install VeganStyle font to user fonts
FONT_DIR="$HOME/.local/share/fonts"
mkdir -p "$FONT_DIR"
cp "$SCRIPT_DIR/assets/VeganStyle.ttf" "$FONT_DIR/"
fc-cache -f 2>/dev/null || true
echo "Font installed to $FONT_DIR"

# Install desktop entry
DESKTOP_DIR="$HOME/.local/share/applications"
mkdir -p "$DESKTOP_DIR"
cp "$SCRIPT_DIR/pikapika.desktop" "$DESKTOP_DIR/"
echo "Desktop entry installed to $DESKTOP_DIR"

echo "Pikapika installed successfully."
