#!/bin/bash
set -e

rm -rf "$HOME/.local/share/pikapika"
echo "App removed"

rm -f "$HOME/.local/bin/pikapika"
echo "Launcher removed"

rm -f "$HOME/.local/share/fonts/VeganStyle.ttf"
fc-cache -f 2>/dev/null || true
echo "Font removed"

rm -f "$HOME/.local/share/icons/hicolor/scalable/apps/pikapika.svg"
echo "Icon removed"

rm -f "$HOME/.local/share/applications/pikapika.desktop"
echo "Desktop entry removed"

echo "Pikapika uninstalled."
