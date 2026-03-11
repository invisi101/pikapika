#!/bin/bash
set -e

rm -f "$HOME/.local/share/fonts/VeganStyle.ttf"
fc-cache -f 2>/dev/null || true
echo "Font removed"

rm -f "$HOME/.local/share/applications/pikapika.desktop"
echo "Desktop entry removed"

echo "Pikapika uninstalled."
