# Pikapika

**File metadata viewer & stripper** — a GTK4/Libadwaita app to inspect and remove metadata from images, documents, and other files.

<p align="center">
  <img src="assets/pikapika.svg" width="200" alt="Pikapika">
</p>

## Features

| Mode | Description |
|------|-------------|
| **View Metadata** | Open a single file, inspect all metadata fields with checkboxes, selectively strip chosen fields via exiftool |
| **Strip Metadata** | Bulk-select multiple files, remove all metadata at once via mat2 |
| **Folder Audit** | Recursively scan a directory and flag every file that contains metadata |
| **Compare** | Side-by-side metadata diff of two files, colour-coded by status |

- Neon dark theme matching the [DD-imager](https://github.com/invisi101/DD-imager) / [bigsnatch](https://github.com/invisi101/bigsnatch) aesthetic
- Selective field stripping powered by [exiftool](https://exiftool.org/)
- Full metadata removal powered by [mat2](https://0xacab.org/jvoisin/mat2)
- Export metadata or reports to JSON from any mode
- Confirmation dialogs before any destructive operation
- Per-file success/failure reporting for bulk operations
- Graceful handling of unsupported file types and empty metadata

## Install

```bash
git clone https://github.com/invisi101/pikapika.git
cd pikapika
bash install.sh
```

This installs the app to `~/.local/share/pikapika/`, creates a `pikapika` command in `~/.local/bin/`, and adds a desktop entry, icon, and font to `~/.local/`. The cloned repo can be removed after install.

## Uninstall

```bash
bash uninstall.sh
```

## Usage

```bash
pikapika
```

Or launch **Pikapika** from your application menu.

### View Metadata

Select a file to inspect. All metadata fields are listed with checkboxes. Use **Select All** / **Deselect All** to toggle, then **Strip Selected** to remove only the chosen fields. **Export JSON** saves all metadata to a file. Requires `exiftool` for selective stripping — if unavailable, offers a mat2 fallback that strips everything.

### Strip Metadata

Select one or more files. Review the file list, then **Strip All Metadata** to remove everything. Uses mat2 under the hood — replaces each file in-place with its cleaned version.

### Folder Audit

Select a directory to scan recursively. Every file is checked for metadata and categorised as clean, containing metadata (with field count), or unsupported. Summary stats at the top, exportable report. Double-click any file to jump straight to the View Metadata page.

### Compare Metadata

Pick two files to diff. All metadata keys are shown side-by-side, colour-coded: yellow for different values, pink for only-in-A, cyan for only-in-B, grey for identical. Exportable as JSON.

## Dependencies

| Package | Purpose |
|---------|---------|
| `python-gobject` | GTK4/Libadwaita bindings |
| `libadwaita` | Adwaita widget library |
| `mat2` | Metadata parsing and removal |
| `perl-image-exiftool` | Selective metadata field stripping |

## License

[GPL-3.0](LICENSE)
