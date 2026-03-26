#!/usr/bin/env python3
"""Pikapika — Metadata Viewer & Stripper."""

import json
import os
import shutil
import subprocess
import threading
import urllib.request
import urllib.parse
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, Pango, PangoCairo, Gdk

from libmat2 import parser_factory


# ---- Exiftool tag group mapping ----

_MAT2_TO_EXIFTOOL_GROUP = {
    'Exif': 'EXIF',
    'Xmp': 'XMP',
    'Iptc': 'IPTC',
    'Icc': 'ICC_Profile',
    'Pdf': 'PDF',
    'Photoshop': 'Photoshop',
}


def _mat2_key_to_exiftool_arg(key):
    """Convert mat2-style key like 'Exif.Image.Make' to exiftool arg like '-EXIF:Make='."""
    parts = key.split('.')
    if len(parts) >= 2:
        group = _MAT2_TO_EXIFTOOL_GROUP.get(parts[0])
        tag = parts[-1]
        if group:
            return f'-{group}:{tag}='
    tag = parts[-1] if '.' in key else key
    return f'-{tag}='


# ---- Config persistence ----

_CONFIG_DIR = Path.home() / '.config' / 'pikapika'
_CONFIG_FILE = _CONFIG_DIR / 'config.json'


def _load_config():
    try:
        return json.loads(_CONFIG_FILE.read_text())
    except (FileNotFoundError, json.JSONDecodeError, OSError):
        return {}


def _save_config(config):
    _CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    _CONFIG_FILE.write_text(json.dumps(config, indent=2))


CUSTOM_CSS = """
/* ==== Pikapika Neon Theme ==== */

@define-color accent_bg_color #818cf8;
@define-color accent_fg_color #ffffff;
@define-color accent_color #a5b4fc;
@define-color window_bg_color #0f0f23;
@define-color view_bg_color #141428;
@define-color card_bg_color #1a1a2e;
@define-color headerbar_bg_color #12122a;
@define-color headerbar_fg_color #e0e0ff;
@define-color popover_bg_color #1a1a2e;
@define-color dialog_bg_color #1a1a2e;

/* Window background with subtle radial glow */
window.background {
    background-image:
        radial-gradient(ellipse at 50% 20%, alpha(#818cf8, 0.06) 0%, transparent 70%),
        linear-gradient(180deg, #0f0f23, #12122e);
}

/* Headerbar */
headerbar {
    background-image: linear-gradient(180deg, #1a1a2e, #12122a);
    border-bottom: 1px solid alpha(#818cf8, 0.2);
    box-shadow: 0 1px 8px alpha(#000000, 0.5);
}

headerbar .title {
    color: #e0e0ff;
    font-weight: bold;
    letter-spacing: 0.5px;
}

headerbar button {
    color: #c4c4f0;
}

headerbar button:hover {
    color: #e0e0ff;
    background-color: alpha(#818cf8, 0.15);
}

/* Suggested action — pink-purple gradient */
button.suggested-action {
    background-image: linear-gradient(135deg, #f472b6, #818cf8);
    color: #ffffff;
    border: none;
    box-shadow: 0 2px 10px alpha(#f472b6, 0.35);
    text-shadow: 0 1px 2px alpha(#000000, 0.3);
    font-weight: 600;
    transition: all 200ms ease;
}

button.suggested-action:hover {
    background-image: linear-gradient(135deg, #f9a8d4, #a5b4fc);
    box-shadow: 0 2px 20px alpha(#f472b6, 0.6);
}

button.suggested-action:active {
    background-image: linear-gradient(135deg, #ec4899, #6366f1);
}

/* Destructive action — red glow */
button.destructive-action {
    background-image: linear-gradient(135deg, #ef4444, #b91c1c);
    border: none;
    box-shadow: 0 2px 10px alpha(#ef4444, 0.35);
    font-weight: 600;
    transition: all 200ms ease;
}

button.destructive-action:hover {
    box-shadow: 0 2px 20px alpha(#ef4444, 0.6);
    background-image: linear-gradient(135deg, #f87171, #dc2626);
}

/* Pill buttons */
button.pill {
    border: 1px solid alpha(#818cf8, 0.3);
    transition: all 200ms ease;
}

button.pill:hover {
    border-color: alpha(#818cf8, 0.6);
    box-shadow: 0 0 10px alpha(#818cf8, 0.2);
}

/* Entry fields */
entry {
    background-color: #16213e;
    border: 1px solid #2d2d5e;
    color: #e0e0ff;
    border-radius: 8px;
    caret-color: #818cf8;
    transition: all 200ms ease;
}

entry:focus {
    border-color: #818cf8;
    box-shadow: 0 0 10px alpha(#818cf8, 0.35);
}

/* Cards */
.card {
    background-color: #1a1a2e;
    border: 1px solid alpha(#818cf8, 0.15);
    border-radius: 12px;
    box-shadow: 0 4px 12px alpha(#000000, 0.3);
}

/* Boxed list rows */
.boxed-list {
    background-color: transparent;
}

.boxed-list > row {
    background-color: #1a1a2e;
    border-bottom: 1px solid alpha(#818cf8, 0.08);
    transition: all 150ms ease;
}

.boxed-list > row:selected {
    background-image: linear-gradient(90deg, alpha(#818cf8, 0.15), alpha(#f472b6, 0.08));
    box-shadow: inset 3px 0 0 #818cf8;
}

.boxed-list > row:hover:not(:selected) {
    background-color: alpha(#818cf8, 0.06);
}

/* Titles */
.title-1 {
    color: #e0e0ff;
    font-weight: 800;
    letter-spacing: 0.3px;
}

.title-2 {
    color: #c4c4f0;
    font-weight: 700;
}

.heading {
    color: #f472b6;
    font-weight: 600;
}

.dim-label {
    color: alpha(#c4c4f0, 0.5);
}

.caption {
    font-size: 11px;
}

/* Success — neon green */
.success {
    color: #34d399;
    font-weight: 600;
}

/* Error — neon red */
.error {
    color: #f87171;
    font-weight: 600;
}

/* Warning banner */
.warning-banner {
    background-image: linear-gradient(90deg, alpha(#f59e0b, 0.12), alpha(#ef4444, 0.08));
    border-bottom: 1px solid alpha(#f59e0b, 0.25);
}

.warning-banner label {
    color: #fbbf24;
    font-weight: 600;
}

/* Separator */
separator {
    background-color: alpha(#818cf8, 0.12);
    min-height: 1px;
}

/* Scrollbar */
scrollbar slider {
    background-color: alpha(#818cf8, 0.25);
    border-radius: 4px;
    min-width: 6px;
}

scrollbar slider:hover {
    background-color: alpha(#818cf8, 0.45);
}

/* Alert dialog */
dialog {
    background-color: #1a1a2e;
}

/* ---- Welcome mode cards ---- */
.mode-card {
    background-color: #1a1a2e;
    border: 1px solid alpha(#818cf8, 0.2);
    border-radius: 16px;
    padding: 18px 14px;
    transition: all 200ms ease;
    min-width: 160px;
}

.mode-card:hover {
    border-color: alpha(#818cf8, 0.5);
    box-shadow: 0 4px 20px alpha(#818cf8, 0.2);
    background-color: #1e1e36;
}

.mode-card:active {
    background-color: alpha(#818cf8, 0.1);
}

.mode-card-icon {
    font-size: 36px;
    margin-bottom: 4px;
}

.mode-card-title {
    color: #e0e0ff;
    font-weight: 700;
    font-size: 15px;
}

.mode-card-subtitle {
    color: alpha(#c4c4f0, 0.6);
    font-size: 12px;
}

/* ---- Metadata rows ---- */
.meta-row {
    background-color: #16213e;
    border: 1px solid alpha(#818cf8, 0.1);
    border-radius: 8px;
    padding: 8px 12px;
    margin-top: 2px;
    margin-bottom: 2px;
}

.meta-key {
    color: #f472b6;
    font-weight: 600;
    font-size: 13px;
}

.meta-value {
    color: #c4c4f0;
    font-size: 13px;
}

/* Checkbutton indicator — neon gradient when checked */
checkbutton indicator {
    border-radius: 4px;
    border: 1px solid #2d2d5e;
    background-color: #16213e;
    min-width: 18px;
    min-height: 18px;
}

checkbutton:checked indicator {
    background-image: linear-gradient(135deg, #f472b6, #818cf8);
    border-color: transparent;
    box-shadow: 0 0 6px alpha(#f472b6, 0.4);
}

checkbutton label {
    color: #c4c4f0;
}

/* ---- File list items ---- */
.file-item {
    background-color: #16213e;
    border: 1px solid alpha(#818cf8, 0.1);
    border-radius: 8px;
    padding: 10px 14px;
    margin-top: 2px;
    margin-bottom: 2px;
}

.file-item-name {
    color: #e0e0ff;
    font-weight: 600;
    font-size: 14px;
}

.file-item-path {
    color: alpha(#c4c4f0, 0.5);
    font-size: 11px;
}

/* ---- Result indicators ---- */
.result-success {
    color: #34d399;
    font-weight: 600;
}

.result-fail {
    color: #f87171;
    font-weight: 600;
}

/* ---- Audit rows ---- */
.audit-row {
    background-color: #16213e;
    border: 1px solid alpha(#818cf8, 0.1);
    border-radius: 8px;
    padding: 8px 14px;
    margin-top: 2px;
    margin-bottom: 2px;
}

.audit-clean {
    color: #34d399;
    font-weight: 600;
    font-size: 12px;
}

.audit-dirty {
    color: #f472b6;
    font-weight: 600;
    font-size: 12px;
}

.audit-unsupported {
    color: alpha(#c4c4f0, 0.4);
    font-size: 12px;
}

.audit-field-count {
    color: #818cf8;
    font-weight: 600;
    font-size: 12px;
}

/* ---- Compare columns ---- */
.compare-header {
    background-color: #16213e;
    border: 1px solid alpha(#818cf8, 0.15);
    border-radius: 8px;
    padding: 10px 14px;
}

.compare-only-a {
    color: #f472b6;
}

.compare-only-b {
    color: #06b6d4;
}

.compare-diff {
    color: #fbbf24;
}

.compare-same {
    color: alpha(#c4c4f0, 0.4);
}

/* ---- Summary stats ---- */
.stat-number {
    color: #818cf8;
    font-weight: 800;
    font-size: 28px;
}

.stat-label {
    color: alpha(#c4c4f0, 0.6);
    font-size: 12px;
}
"""


def _load_font():
    """Register VeganStyle font from assets directory."""
    font_path = Path(__file__).parent / 'assets' / 'VeganStyle.ttf'
    if not font_path.exists():
        return
    fontmap = PangoCairo.FontMap.get_default()
    if hasattr(fontmap, 'add_font_file'):
        fontmap.add_font_file(str(font_path))
    else:
        # Fallback: ensure font is in user fonts dir
        user_fonts = Path.home() / '.local' / 'share' / 'fonts'
        dest = user_fonts / 'VeganStyle.ttf'
        if not dest.exists():
            user_fonts.mkdir(parents=True, exist_ok=True)
            shutil.copy2(font_path, dest)
            subprocess.run(['fc-cache', '-f'], capture_output=True)


class PikapikaApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id='com.invisi101.pikapika')
        self.connect('activate', self.on_activate)

    def on_activate(self, app):
        style_manager = Adw.StyleManager.get_default()
        style_manager.set_color_scheme(Adw.ColorScheme.FORCE_DARK)
        self._load_css()
        _load_font()

        self.win = Adw.ApplicationWindow(
            application=app,
            title='Pikapika',
            default_width=640,
            default_height=540,
        )

        # State
        self.current_file = None
        self.current_meta = {}  # flat metadata dict for current file
        self.meta_checks = {}  # key -> CheckButton
        self.strip_files = []  # list of file paths for bulk strip
        self._audit_cancel = threading.Event()
        self._compare_rows = []  # (row_widget, status) for hide-identical
        self._audit_dirty_files = []  # for batch strip

        # Header bar
        self.header = Adw.HeaderBar()
        self.title_label = Gtk.Label(label='Pikapika', css_classes=['title'])
        self.header.set_title_widget(self.title_label)

        self.btn_back = Gtk.Button(icon_name='go-previous-symbolic')
        self.btn_back.connect('clicked', lambda _b: self._go_back())
        self.btn_back.set_visible(False)
        self.header.pack_start(self.btn_back)
        self._nav_history = []

        # Stack
        self.stack = Gtk.Stack()
        self.stack.set_vexpand(True)
        self.stack.set_transition_type(Gtk.StackTransitionType.SLIDE_LEFT_RIGHT)
        self.stack.set_transition_duration(250)

        self.stack.add_named(self._build_welcome_page(), 'welcome')
        self.stack.add_named(self._build_view_metadata_page(), 'view-metadata')
        self.stack.add_named(self._build_view_result_page(), 'view-result')
        self.stack.add_named(self._build_strip_confirm_page(), 'strip-confirm')
        self.stack.add_named(self._build_strip_result_page(), 'strip-result')
        self.stack.add_named(self._build_audit_page(), 'audit')
        self.stack.add_named(self._build_compare_page(), 'compare')
        self.stack.add_named(self._build_location_page(), 'location')
        self.stack.add_named(self._build_about_metadata_page(), 'about-metadata')

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.append(self.header)
        vbox.append(self.stack)

        # Toast overlay wraps the main content
        self.toast_overlay = Adw.ToastOverlay()
        self.toast_overlay.set_child(vbox)
        self.win.set_content(self.toast_overlay)

        self.stack.set_visible_child_name('welcome')
        self.win.present()

    # ---- CSS ----

    def _load_css(self):
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CUSTOM_CSS.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    # ---- Toast ----

    def _show_toast(self, message, timeout=3):
        toast = Adw.Toast(title=message, timeout=timeout)
        self.toast_overlay.add_toast(toast)

    # ---- Config / Remember Directory ----

    def _remember_directory(self, path):
        """Save directory to config. If path is a file, saves parent directory."""
        p = Path(path)
        directory = str(p if p.is_dir() else p.parent)
        config = _load_config()
        config['last_directory'] = directory
        _save_config(config)

    def _get_last_directory_file(self):
        config = _load_config()
        last_dir = config.get('last_directory')
        if last_dir and os.path.isdir(last_dir):
            return Gio.File.new_for_path(last_dir)
        return None

    def _set_dialog_initial_folder(self, dialog):
        folder = self._get_last_directory_file()
        if folder:
            dialog.set_initial_folder(folder)

    # ---- File Validation ----

    def _validate_file(self, filepath, need_write=False):
        """Check file exists and is accessible. Returns error message or None."""
        if not os.path.isfile(filepath):
            return f'File not found: {Path(filepath).name}'
        if not os.access(filepath, os.R_OK):
            return f'Cannot read: {Path(filepath).name}'
        if need_write and not os.access(filepath, os.W_OK):
            return f'Cannot write: {Path(filepath).name}'
        return None

    # ---- Navigation ----

    def _navigate(self, page_name, push_history=True):
        if push_history:
            current = self.stack.get_visible_child_name()
            if current and current != page_name:
                self._nav_history.append(current)
        is_home = page_name == 'welcome'
        self.btn_back.set_visible(not is_home)
        self.title_label.set_label('Pikapika' if is_home else
                                   {'view-metadata': 'View Metadata',
                                    'view-result': 'Result',
                                    'strip-confirm': 'Strip Metadata',
                                    'strip-result': 'Result',
                                    'audit': 'Folder Audit',
                                    'compare': 'Compare Metadata'}.get(page_name, 'Pikapika'))
        self.stack.set_visible_child_name(page_name)

    def _go_back(self):
        if self._nav_history:
            self._navigate(self._nav_history.pop(), push_history=False)
        else:
            self._navigate('welcome', push_history=False)

    def _go_home(self):
        self._nav_history.clear()
        self._navigate('welcome', push_history=False)

    # ---- Welcome Page ----

    def _build_welcome_page(self):
        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        # Title top-left in VeganStyle font, pink like bigsnatch
        heading = Gtk.Label()
        heading.set_markup(
            '<span font_family="Vegan Style Personal Use" size="30000" foreground="#f472b6">Pikapika</span>'
        )
        heading.set_halign(Gtk.Align.START)
        heading.set_margin_start(24)
        heading.set_margin_top(16)
        page.append(heading)

        # Cards centered in remaining space — 2x2 grid
        cards_grid = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            spacing=16,
            vexpand=True,
        )

        top_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.CENTER, spacing=12)
        bottom_row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.CENTER, spacing=12)

        def _make_card(icon_markup, title, subtitle, callback):
            card = Gtk.Button()
            card.add_css_class('mode-card')
            card.set_has_frame(False)
            box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6,
                          halign=Gtk.Align.CENTER)
            icon = Gtk.Label()
            icon.add_css_class('mode-card-icon')
            icon.set_markup(icon_markup)
            box.append(icon)
            t = Gtk.Label(label=title)
            t.add_css_class('mode-card-title')
            box.append(t)
            s = Gtk.Label(label=subtitle)
            s.add_css_class('mode-card-subtitle')
            s.set_wrap(True)
            s.set_max_width_chars(18)
            s.set_justify(Gtk.Justification.CENTER)
            box.append(s)
            card.set_child(box)
            card.connect('clicked', lambda _b: callback())
            return card

        top_row.append(_make_card(
            '<span size="xx-large" weight="bold">\U0001f50d</span>',
            'View Metadata', 'Inspect and selectively strip metadata fields',
            self._on_view_metadata))
        top_row.append(_make_card(
            '<span size="xx-large" weight="bold">\u2702</span>',
            'Strip Metadata', 'Remove all metadata from one or more files',
            self._on_strip_metadata))
        top_row.append(_make_card(
            '<span size="xx-large" weight="bold">\U0001f4c1</span>',
            'Folder Audit', 'Scan a folder for files containing metadata',
            self._on_folder_audit))
        bottom_row.append(_make_card(
            '<span size="xx-large" weight="bold">\u2194</span>',
            'Compare', 'Side-by-side metadata diff of two files',
            self._on_compare_metadata))
        bottom_row.append(_make_card(
            '<span size="xx-large" weight="bold">\U0001f4cd</span>',
            'Location Finder', 'Find where a photo was taken from GPS data',
            self._on_location_finder))
        bottom_row.append(_make_card(
            '<span size="xx-large" weight="bold">\u2139</span>',
            'About Metadata', 'Learn what metadata is and why it matters',
            self._on_about_metadata))

        cards_grid.append(top_row)
        cards_grid.append(bottom_row)
        page.append(cards_grid)

        # Drag-and-drop on welcome page
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect('drop', self._on_welcome_drop)
        page.add_controller(drop_target)

        return page

    # ---- View Metadata Page ----

    def _build_view_metadata_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # File info bar
        self.view_file_info = Gtk.Label(
            label='',
            halign=Gtk.Align.START,
            margin_top=12, margin_bottom=8, margin_start=20, margin_end=20,
        )
        self.view_file_info.add_css_class('heading')
        self.view_file_info.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        page.append(self.view_file_info)

        self.view_mime_label = Gtk.Label(
            label='',
            halign=Gtk.Align.START,
            margin_start=20, margin_end=20, margin_bottom=8,
        )
        self.view_mime_label.add_css_class('dim-label')
        page.append(self.view_mime_label)

        page.append(Gtk.Separator())

        # Select All / Deselect All buttons
        btn_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.START,
            spacing=8,
            margin_top=8, margin_start=20, margin_end=20,
        )

        self.btn_select_all = Gtk.Button(label='Select All')
        self.btn_select_all.add_css_class('pill')
        self.btn_select_all.connect('clicked', lambda _b: self._toggle_all_checks(True))
        btn_row.append(self.btn_select_all)

        self.btn_deselect_all = Gtk.Button(label='Deselect All')
        self.btn_deselect_all.add_css_class('pill')
        self.btn_deselect_all.connect('clicked', lambda _b: self._toggle_all_checks(False))
        btn_row.append(self.btn_deselect_all)

        spacer = Gtk.Box(hexpand=True)
        btn_row.append(spacer)

        self.btn_export = Gtk.Button(label='Export JSON')
        self.btn_export.add_css_class('pill')
        self.btn_export.add_css_class('suggested-action')
        self.btn_export.set_sensitive(False)
        self.btn_export.connect('clicked', lambda _b: self._on_export_json())
        btn_row.append(self.btn_export)

        page.append(btn_row)

        # Scrollable metadata list
        scrolled = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            margin_top=8, margin_bottom=8, margin_start=16, margin_end=16,
        )
        self.meta_list_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=4, margin_bottom=4, margin_start=4, margin_end=4,
        )
        scrolled.set_child(self.meta_list_box)
        page.append(scrolled)

        # Loading spinner (shown while reading metadata)
        self.view_spinner = Gtk.Spinner(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.view_spinner.set_size_request(32, 32)
        self.view_spinner.set_visible(False)
        page.append(self.view_spinner)

        # Status label for empty/error states
        self.view_status_label = Gtk.Label(
            label='',
            halign=Gtk.Align.CENTER,
            margin_top=8, margin_bottom=8,
        )
        self.view_status_label.set_visible(False)
        page.append(self.view_status_label)

        # Strip Selected button
        self.btn_strip_selected = Gtk.Button(label='Strip Selected')
        self.btn_strip_selected.add_css_class('destructive-action')
        self.btn_strip_selected.add_css_class('pill')
        self.btn_strip_selected.set_margin_bottom(16)
        self.btn_strip_selected.set_margin_start(20)
        self.btn_strip_selected.set_margin_end(20)
        self.btn_strip_selected.set_halign(Gtk.Align.CENTER)
        self.btn_strip_selected.connect('clicked', lambda _b: self._on_strip_selected())
        page.append(self.btn_strip_selected)

        # Drag-and-drop on view-metadata page
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect('drop', self._on_view_drop)
        page.add_controller(drop_target)

        return page

    # ---- View Result Page (with before/after removed fields) ----

    def _build_view_result_page(self):
        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
        )

        # Top section: icon + message
        top_section = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.CENTER,
            spacing=16,
            margin_top=24,
        )

        self.view_result_icon = Gtk.Label()
        self.view_result_icon.set_markup('<span size="30000">\u2714</span>')
        top_section.append(self.view_result_icon)

        self.view_result_label = Gtk.Label(label='')
        self.view_result_label.add_css_class('title-2')
        self.view_result_label.set_wrap(True)
        self.view_result_label.set_max_width_chars(45)
        self.view_result_label.set_justify(Gtk.Justification.CENTER)
        top_section.append(self.view_result_label)

        self.view_result_detail = Gtk.Label(label='')
        self.view_result_detail.add_css_class('dim-label')
        self.view_result_detail.set_wrap(True)
        self.view_result_detail.set_max_width_chars(50)
        self.view_result_detail.set_justify(Gtk.Justification.CENTER)
        top_section.append(self.view_result_detail)

        page.append(top_section)

        # Removed fields section (hidden by default)
        self.removed_fields_heading = Gtk.Label(
            label='Removed Fields',
            halign=Gtk.Align.START,
            margin_top=16, margin_start=20, margin_bottom=4,
        )
        self.removed_fields_heading.add_css_class('heading')
        self.removed_fields_heading.set_visible(False)
        page.append(self.removed_fields_heading)

        self.removed_fields_scroll = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            margin_top=4, margin_bottom=8, margin_start=16, margin_end=16,
        )
        self.removed_fields_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=4, margin_bottom=4, margin_start=4, margin_end=4,
        )
        self.removed_fields_scroll.set_child(self.removed_fields_list)
        self.removed_fields_scroll.set_visible(False)
        page.append(self.removed_fields_scroll)

        btn_home = Gtk.Button(label='Back to Home')
        btn_home.add_css_class('suggested-action')
        btn_home.add_css_class('pill')
        btn_home.set_margin_bottom(16)
        btn_home.set_halign(Gtk.Align.CENTER)
        btn_home.connect('clicked', lambda _b: self._go_home())
        page.append(btn_home)

        return page

    # ---- Strip Confirm Page ----

    def _build_strip_confirm_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Warning banner
        warning_box = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, halign=Gtk.Align.FILL)
        warning_box.add_css_class('warning-banner')
        warning_label = Gtk.Label(
            label='\u26a0  This will permanently remove all metadata from the selected files',
            halign=Gtk.Align.CENTER,
            hexpand=True,
            margin_top=10, margin_bottom=10, margin_start=12, margin_end=12,
        )
        warning_box.append(warning_label)
        page.append(warning_box)

        heading = Gtk.Label(
            label='Files to strip',
            halign=Gtk.Align.START,
            margin_top=16, margin_start=20,
        )
        heading.add_css_class('title-2')
        page.append(heading)

        # File list
        scrolled = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            margin_top=8, margin_bottom=8, margin_start=16, margin_end=16,
        )
        self.strip_file_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=4, margin_bottom=4, margin_start=4, margin_end=4,
        )
        scrolled.set_child(self.strip_file_list)
        page.append(scrolled)

        # Strip All button
        self.btn_strip_all = Gtk.Button(label='Strip All Metadata')
        self.btn_strip_all.add_css_class('destructive-action')
        self.btn_strip_all.add_css_class('pill')
        self.btn_strip_all.set_margin_bottom(16)
        self.btn_strip_all.set_margin_start(20)
        self.btn_strip_all.set_margin_end(20)
        self.btn_strip_all.set_halign(Gtk.Align.CENTER)
        self.btn_strip_all.connect('clicked', lambda _b: self._on_strip_all_confirm())
        page.append(self.btn_strip_all)

        # Drag-and-drop on strip-confirm page
        drop_target = Gtk.DropTarget.new(Gdk.FileList, Gdk.DragAction.COPY)
        drop_target.connect('drop', self._on_strip_confirm_drop)
        page.add_controller(drop_target)

        return page

    # ---- Strip Result Page ----

    def _build_strip_result_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        heading = Gtk.Label(
            label='Results',
            halign=Gtk.Align.START,
            margin_top=16, margin_start=20, margin_bottom=8,
        )
        heading.add_css_class('title-2')
        page.append(heading)

        scrolled = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            margin_top=4, margin_bottom=8, margin_start=16, margin_end=16,
        )
        self.strip_result_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=4, margin_bottom=4, margin_start=4, margin_end=4,
        )
        scrolled.set_child(self.strip_result_list)
        page.append(scrolled)

        btn_home = Gtk.Button(label='Back to Home')
        btn_home.add_css_class('suggested-action')
        btn_home.add_css_class('pill')
        btn_home.set_margin_bottom(16)
        btn_home.set_halign(Gtk.Align.CENTER)
        btn_home.connect('clicked', lambda _b: self._go_home())
        page.append(btn_home)

        return page

    # ---- Drag-and-Drop Handlers ----

    def _on_welcome_drop(self, target, value, x, y):
        files = value.get_files()
        paths = [f.get_path() for f in files if f.get_path()]
        if not paths:
            return False
        if len(paths) == 1:
            self.current_file = paths[0]
            self._remember_directory(paths[0])
            self._load_metadata(paths[0])
        else:
            self.strip_files = paths
            self._remember_directory(paths[0])
            self._populate_strip_file_list()
            self._navigate('strip-confirm')
        return True

    def _on_view_drop(self, target, value, x, y):
        files = value.get_files()
        if files:
            path = files[0].get_path()
            if path:
                self.current_file = path
                self._remember_directory(path)
                self._load_metadata(path)
                return True
        return False

    def _on_strip_confirm_drop(self, target, value, x, y):
        files = value.get_files()
        paths = [f.get_path() for f in files if f.get_path()]
        if not paths:
            return False
        self.strip_files.extend(paths)
        self._remember_directory(paths[0])
        self._populate_strip_file_list()
        return True

    # ---- View Metadata Flow ----

    def _on_view_metadata(self):
        dialog = Gtk.FileDialog()
        dialog.set_title('Select a file to inspect')
        self._set_dialog_initial_folder(dialog)
        dialog.open(self.win, None, self._on_view_file_chosen)

    def _on_view_file_chosen(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        self._remember_directory(path)
        self.current_file = path
        self._load_metadata(path)

    def _load_metadata(self, filepath):
        # Pre-flight validation
        error = self._validate_file(filepath)
        if error:
            self.view_file_info.set_label(Path(filepath).name)
            self.view_mime_label.set_label('')
            self._clear_meta_list()
            self._navigate('view-metadata')
            self._show_meta_error(error)
            return

        self.view_file_info.set_label(Path(filepath).name)
        self.view_mime_label.set_label('')
        self._clear_meta_list()
        self.view_spinner.set_visible(True)
        self.view_spinner.start()
        self.view_status_label.set_visible(False)
        self.btn_strip_selected.set_sensitive(False)
        self.btn_select_all.set_sensitive(False)
        self.btn_deselect_all.set_sensitive(False)
        self.btn_export.set_sensitive(False)
        self._navigate('view-metadata')

        def worker():
            try:
                parser, mtype = parser_factory.get_parser(filepath)
                if parser is None:
                    GLib.idle_add(self._show_meta_error,
                                  f'Unsupported file type: {mtype or "unknown"}')
                    return
                meta = parser.get_meta()
                GLib.idle_add(self._populate_metadata, meta, mtype)
            except Exception as e:
                GLib.idle_add(self._show_meta_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _clear_meta_list(self):
        while child := self.meta_list_box.get_first_child():
            self.meta_list_box.remove(child)
        self.meta_checks.clear()

    def _show_meta_error(self, message):
        self.view_spinner.stop()
        self.view_spinner.set_visible(False)
        self.view_status_label.set_label(message)
        self.view_status_label.remove_css_class('dim-label')
        self.view_status_label.add_css_class('error')
        self.view_status_label.set_visible(True)

    def _populate_metadata(self, meta, mtype):
        self.view_spinner.stop()
        self.view_spinner.set_visible(False)
        self.view_mime_label.set_label(mtype or '')

        if not meta:
            self.current_meta = {}
            self.view_status_label.set_markup(
                '<span size="x-large" foreground="#e0e0ff" weight="bold">No metadata found</span>'
            )
            self.view_status_label.remove_css_class('error')
            self.view_status_label.remove_css_class('dim-label')
            self.view_status_label.set_visible(True)
            self.view_status_label.set_vexpand(True)
            self.view_status_label.set_valign(Gtk.Align.CENTER)
            return

        # Flatten nested dicts
        flat = {}
        for k, v in meta.items():
            if isinstance(v, dict):
                for sk, sv in v.items():
                    flat[f'{k}.{sk}'] = str(sv)
            else:
                flat[k] = str(v)

        self.current_meta = flat

        for key, value in flat.items():
            row = Gtk.Box(
                orientation=Gtk.Orientation.HORIZONTAL,
                spacing=10,
            )
            row.add_css_class('meta-row')

            check = Gtk.CheckButton()
            check.set_active(False)
            row.append(check)
            self.meta_checks[key] = check

            key_label = Gtk.Label(label=key, halign=Gtk.Align.START)
            key_label.add_css_class('meta-key')
            key_label.set_size_request(180, -1)
            key_label.set_ellipsize(Pango.EllipsizeMode.END)
            key_label.set_xalign(0)
            row.append(key_label)

            val_label = Gtk.Label(label=value, halign=Gtk.Align.START, hexpand=True)
            val_label.add_css_class('meta-value')
            val_label.set_ellipsize(Pango.EllipsizeMode.END)
            val_label.set_xalign(0)
            row.append(val_label)

            self.meta_list_box.append(row)

        self.btn_strip_selected.set_sensitive(True)
        self.btn_select_all.set_sensitive(True)
        self.btn_deselect_all.set_sensitive(True)
        self.btn_export.set_sensitive(True)

    def _toggle_all_checks(self, state):
        for check in self.meta_checks.values():
            check.set_active(state)

    # ---- Before/After Helper ----

    def _compute_removed_fields(self, filepath, pre_meta):
        """Re-read metadata after strip and return dict of fields that were removed."""
        try:
            parser, _ = parser_factory.get_parser(filepath)
            if parser is None:
                return pre_meta
            meta = parser.get_meta()
            flat = {}
            for k, v in meta.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        flat[f'{k}.{sk}'] = str(sv)
                else:
                    flat[k] = str(v)
            removed = {}
            for k, v in pre_meta.items():
                if k not in flat:
                    removed[k] = v
            return removed
        except Exception:
            return pre_meta

    # ---- Selective Strip ----

    def _on_strip_selected(self):
        selected = [k for k, cb in self.meta_checks.items() if cb.get_active()]
        if not selected:
            return

        dialog = Adw.AlertDialog(
            heading='Strip selected metadata?',
            body=f'This will remove {len(selected)} metadata field(s) from the file. This cannot be undone.',
        )
        dialog.add_response('cancel', 'Cancel')
        dialog.add_response('strip', 'Strip')
        dialog.set_response_appearance('strip', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.choose(self.win, None, lambda d, r: self._on_strip_selected_response(d, r, selected))

    def _on_strip_selected_response(self, dialog, result, selected):
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 'strip':
            return

        filepath = self.current_file

        # Pre-flight validation
        error = self._validate_file(filepath, need_write=True)
        if error:
            self._show_view_result(False, 'Cannot strip', error)
            return

        # If all fields selected, use mat2 for complete removal
        # (exiftool can't delete protected/permanent/ICC tags individually)
        all_selected = len(selected) == len(self.meta_checks)
        if all_selected:
            self._strip_file_mat2(filepath, show_view_result=True)
            return

        has_exiftool = shutil.which('exiftool') is not None

        if not has_exiftool:
            self._offer_mat2_fallback()
            return

        pre_strip_meta = dict(self.current_meta)

        def worker():
            try:
                # Build exiftool args with smarter tag mapping
                args = ['exiftool', '-overwrite_original']
                for key in selected:
                    args.append(_mat2_key_to_exiftool_arg(key))
                args.append(filepath)

                proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
                if proc.returncode == 0:
                    removed = self._compute_removed_fields(filepath, pre_strip_meta)
                    GLib.idle_add(self._show_view_result, True,
                                  f'Stripped {len(selected)} field(s)',
                                  Path(filepath).name, removed)
                else:
                    GLib.idle_add(self._show_view_result, False,
                                  'exiftool error',
                                  proc.stderr.strip() or proc.stdout.strip())
            except Exception as e:
                GLib.idle_add(self._show_view_result, False, 'Error', str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _offer_mat2_fallback(self):
        dialog = Adw.AlertDialog(
            heading='exiftool not found',
            body='Selective stripping requires exiftool. Would you like to strip ALL metadata using mat2 instead?',
        )
        dialog.add_response('cancel', 'Cancel')
        dialog.add_response('strip', 'Strip All')
        dialog.set_response_appearance('strip', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.choose(self.win, None, self._on_mat2_fallback_response)

    def _on_mat2_fallback_response(self, dialog, result):
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 'strip':
            return
        self._strip_file_mat2(self.current_file, show_view_result=True)

    def _strip_file_mat2(self, filepath, show_view_result=False):
        # Pre-flight validation
        error = self._validate_file(filepath, need_write=True)
        if error:
            if show_view_result:
                self._show_view_result(False, 'Cannot strip', error)
                return
            return False, filepath, error

        pre_strip_meta = dict(self.current_meta) if show_view_result else None

        def worker():
            try:
                parser, mtype = parser_factory.get_parser(filepath)
                if parser is None:
                    msg = f'Unsupported: {mtype or "unknown"}'
                    if show_view_result:
                        GLib.idle_add(self._show_view_result, False, msg, filepath)
                    return False, filepath, msg

                success = parser.remove_all()
                if success:
                    output = parser.output_filename
                    shutil.move(output, filepath)
                    msg = 'All metadata removed'
                    if show_view_result:
                        removed = self._compute_removed_fields(filepath, pre_strip_meta)
                        GLib.idle_add(self._show_view_result, True, msg,
                                      Path(filepath).name, removed)
                    return True, filepath, msg
                else:
                    msg = 'mat2 failed to clean file'
                    if show_view_result:
                        GLib.idle_add(self._show_view_result, False, msg, filepath)
                    return False, filepath, msg
            except Exception as e:
                msg = str(e)
                if show_view_result:
                    GLib.idle_add(self._show_view_result, False, msg, filepath)
                return False, filepath, msg

        if show_view_result:
            threading.Thread(target=worker, daemon=True).start()
        else:
            return worker()

    def _show_view_result(self, success, message, detail, removed_fields=None):
        if success:
            self.view_result_icon.set_markup('<span size="30000" foreground="#34d399">\u2714</span>')
            self.view_result_label.set_label(message)
            self.view_result_label.remove_css_class('error')
            self.view_result_label.add_css_class('result-success')
        else:
            self.view_result_icon.set_markup('<span size="30000" foreground="#f87171">\u2718</span>')
            self.view_result_label.set_label(message)
            self.view_result_label.remove_css_class('result-success')
            self.view_result_label.add_css_class('result-fail')
        self.view_result_detail.set_label(detail)

        # Populate removed fields section
        while child := self.removed_fields_list.get_first_child():
            self.removed_fields_list.remove(child)

        if removed_fields:
            self.removed_fields_heading.set_visible(True)
            self.removed_fields_scroll.set_visible(True)
            for key, value in removed_fields.items():
                row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
                row.add_css_class('meta-row')
                key_label = Gtk.Label(label=key, halign=Gtk.Align.START)
                key_label.add_css_class('meta-key')
                key_label.set_size_request(180, -1)
                key_label.set_ellipsize(Pango.EllipsizeMode.END)
                key_label.set_xalign(0)
                row.append(key_label)
                val_label = Gtk.Label(label=value, halign=Gtk.Align.START, hexpand=True)
                val_label.add_css_class('meta-value')
                val_label.set_ellipsize(Pango.EllipsizeMode.END)
                val_label.set_xalign(0)
                row.append(val_label)
                self.removed_fields_list.append(row)
        else:
            self.removed_fields_heading.set_visible(False)
            self.removed_fields_scroll.set_visible(False)

        self._navigate('view-result')

    # ---- Strip Metadata Flow ----

    def _on_strip_metadata(self):
        dialog = Gtk.FileDialog()
        dialog.set_title('Select files to strip')
        self._set_dialog_initial_folder(dialog)
        dialog.open_multiple(self.win, None, self._on_strip_files_chosen)

    def _on_strip_files_chosen(self, dialog, result):
        try:
            gfiles = dialog.open_multiple_finish(result)
        except GLib.Error:
            return

        self.strip_files = []
        for i in range(gfiles.get_n_items()):
            gfile = gfiles.get_item(i)
            path = gfile.get_path()
            if path:
                self.strip_files.append(path)

        if not self.strip_files:
            return

        self._remember_directory(self.strip_files[0])
        self._populate_strip_file_list()
        self._navigate('strip-confirm')

    def _populate_strip_file_list(self):
        while child := self.strip_file_list.get_first_child():
            self.strip_file_list.remove(child)

        for filepath in self.strip_files:
            p = Path(filepath)
            row = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2)
            row.add_css_class('file-item')

            name_label = Gtk.Label(label=p.name, halign=Gtk.Align.START)
            name_label.add_css_class('file-item-name')
            name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            row.append(name_label)

            path_label = Gtk.Label(label=str(p.parent), halign=Gtk.Align.START)
            path_label.add_css_class('file-item-path')
            path_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            row.append(path_label)

            self.strip_file_list.append(row)

    def _on_strip_all_confirm(self):
        dialog = Adw.AlertDialog(
            heading='Strip all metadata?',
            body=f'This will permanently remove all metadata from {len(self.strip_files)} file(s). This cannot be undone.',
        )
        dialog.add_response('cancel', 'Cancel')
        dialog.add_response('strip', 'Strip All')
        dialog.set_response_appearance('strip', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.choose(self.win, None, self._on_strip_all_response)

    def _on_strip_all_response(self, dialog, result):
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 'strip':
            return

        files = list(self.strip_files)

        def worker():
            results = []
            for filepath in files:
                # Pre-flight validation
                error = self._validate_file(filepath, need_write=True)
                if error:
                    results.append((False, filepath, error))
                    continue
                try:
                    parser, mtype = parser_factory.get_parser(filepath)
                    if parser is None:
                        results.append((False, filepath, f'Unsupported: {mtype or "unknown"}'))
                        continue
                    success = parser.remove_all()
                    if success:
                        shutil.move(parser.output_filename, filepath)
                        results.append((True, filepath, 'All metadata removed'))
                    else:
                        results.append((False, filepath, 'mat2 failed to clean'))
                except Exception as e:
                    results.append((False, filepath, str(e)))
            GLib.idle_add(self._show_strip_results, results)

        threading.Thread(target=worker, daemon=True).start()

    def _show_strip_results(self, results):
        while child := self.strip_result_list.get_first_child():
            self.strip_result_list.remove(child)

        for success, filepath, message in results:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class('file-item')

            icon = Gtk.Label()
            if success:
                icon.set_markup('<span foreground="#34d399">\u2714</span>')
            else:
                icon.set_markup('<span foreground="#f87171">\u2718</span>')
            row.append(icon)

            info_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=2, hexpand=True)

            name_label = Gtk.Label(label=Path(filepath).name, halign=Gtk.Align.START)
            name_label.add_css_class('file-item-name')
            name_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            info_box.append(name_label)

            status_label = Gtk.Label(label=message, halign=Gtk.Align.START)
            status_label.add_css_class('result-success' if success else 'result-fail')
            status_label.set_ellipsize(Pango.EllipsizeMode.END)
            info_box.append(status_label)

            row.append(info_box)
            self.strip_result_list.append(row)

        self._navigate('strip-result')

    # ---- Export JSON ----

    def _on_export_json(self):
        if not self.current_meta or not self.current_file:
            return
        dialog = Gtk.FileDialog()
        dialog.set_title('Save metadata as JSON')
        self._set_dialog_initial_folder(dialog)
        stem = Path(self.current_file).stem
        dialog.set_initial_name(f'{stem}_metadata.json')
        dialog.save(self.win, None, self._on_export_save)

    def _on_export_save(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        self._remember_directory(path)
        export = {
            'file': self.current_file,
            'metadata': self.current_meta,
        }
        try:
            with open(path, 'w') as f:
                json.dump(export, f, indent=2, ensure_ascii=False)
            self._show_view_result(True, 'Metadata exported', path)
        except Exception as e:
            self._show_view_result(False, 'Export failed', str(e))

    # ---- Folder Audit ----

    def _on_folder_audit(self):
        dialog = Gtk.FileDialog()
        dialog.set_title('Select a folder to audit')
        self._set_dialog_initial_folder(dialog)
        dialog.select_folder(self.win, None, self._on_audit_folder_chosen)

    def _on_audit_folder_chosen(self, dialog, result):
        try:
            gfile = dialog.select_folder_finish(result)
        except GLib.Error:
            return
        folder = gfile.get_path()
        self._remember_directory(folder)
        self._navigate('audit')
        self._run_audit(folder)

    def _build_audit_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # Summary bar
        self.audit_summary = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.CENTER,
            spacing=32,
            margin_top=16, margin_bottom=8,
        )
        page.append(self.audit_summary)

        self.audit_folder_label = Gtk.Label(
            label='',
            halign=Gtk.Align.START,
            margin_start=20, margin_end=20, margin_bottom=4,
        )
        self.audit_folder_label.add_css_class('dim-label')
        self.audit_folder_label.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        page.append(self.audit_folder_label)

        page.append(Gtk.Separator())

        # Spinner
        self.audit_spinner = Gtk.Spinner(halign=Gtk.Align.CENTER, margin_top=16)
        self.audit_spinner.set_size_request(32, 32)
        self.audit_spinner.set_visible(False)
        page.append(self.audit_spinner)

        self.audit_progress_label = Gtk.Label(
            label='', halign=Gtk.Align.CENTER, margin_top=4,
        )
        self.audit_progress_label.add_css_class('dim-label')
        self.audit_progress_label.set_visible(False)
        page.append(self.audit_progress_label)

        # Cancel button (visible during scan)
        self.btn_audit_cancel = Gtk.Button(label='Cancel Scan')
        self.btn_audit_cancel.add_css_class('destructive-action')
        self.btn_audit_cancel.add_css_class('pill')
        self.btn_audit_cancel.set_halign(Gtk.Align.CENTER)
        self.btn_audit_cancel.set_margin_top(8)
        self.btn_audit_cancel.set_visible(False)
        self.btn_audit_cancel.connect('clicked', lambda _b: self._cancel_audit())
        page.append(self.btn_audit_cancel)

        # Scrollable results
        scrolled = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            margin_top=8, margin_bottom=8, margin_start=16, margin_end=16,
        )
        self.audit_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=4, margin_bottom=4, margin_start=4, margin_end=4,
        )
        scrolled.set_child(self.audit_list)
        page.append(scrolled)

        # Bottom buttons
        btn_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.CENTER,
            spacing=12,
            margin_bottom=16,
        )
        btn_home = Gtk.Button(label='Back to Home')
        btn_home.add_css_class('suggested-action')
        btn_home.add_css_class('pill')
        btn_home.connect('clicked', lambda _b: self._go_home())
        btn_row.append(btn_home)

        self.btn_audit_export = Gtk.Button(label='Export Report')
        self.btn_audit_export.add_css_class('pill')
        self.btn_audit_export.set_sensitive(False)
        self.btn_audit_export.connect('clicked', lambda _b: self._on_audit_export())
        btn_row.append(self.btn_audit_export)

        self.btn_audit_strip = Gtk.Button(label='Strip All Dirty Files')
        self.btn_audit_strip.add_css_class('destructive-action')
        self.btn_audit_strip.add_css_class('pill')
        self.btn_audit_strip.set_sensitive(False)
        self.btn_audit_strip.connect('clicked', lambda _b: self._on_audit_batch_strip())
        btn_row.append(self.btn_audit_strip)

        self.btn_audit_rescan = Gtk.Button(label='Re-scan Folder')
        self.btn_audit_rescan.add_css_class('pill')
        self.btn_audit_rescan.set_sensitive(False)
        self.btn_audit_rescan.connect('clicked', lambda _b: self._on_audit_rescan())
        btn_row.append(self.btn_audit_rescan)

        page.append(btn_row)
        return page

    def _cancel_audit(self):
        self._audit_cancel.set()

    def _run_audit(self, folder):
        # Clear previous
        while child := self.audit_list.get_first_child():
            self.audit_list.remove(child)
        while child := self.audit_summary.get_first_child():
            self.audit_summary.remove(child)
        self.audit_folder_label.set_label(folder)
        self.audit_spinner.set_visible(True)
        self.audit_spinner.start()
        self.audit_progress_label.set_visible(True)
        self.audit_progress_label.set_label('Scanning...')
        self.btn_audit_export.set_sensitive(False)
        self.btn_audit_strip.set_sensitive(False)
        self.btn_audit_cancel.set_visible(True)
        self._audit_cancel.clear()
        self.audit_results = []

        def worker():
            results = []
            count = 0
            # Lazy rglob: iterate generator instead of eager list
            for filepath in Path(folder).rglob('*'):
                if self._audit_cancel.is_set():
                    GLib.idle_add(self._show_audit_results, results, folder, True)
                    return
                if not filepath.is_file():
                    continue
                count += 1
                if count % 10 == 0:
                    GLib.idle_add(self.audit_progress_label.set_label,
                                  f'Scanning... ({count} files processed)')
                try:
                    parser, mtype = parser_factory.get_parser(str(filepath))
                    if parser is None:
                        results.append((str(filepath), 'unsupported', mtype, 0))
                        continue
                    meta = parser.get_meta()
                    # Flatten
                    field_count = 0
                    for k, v in meta.items():
                        if isinstance(v, dict):
                            field_count += len(v)
                        else:
                            field_count += 1
                    if field_count > 0:
                        results.append((str(filepath), 'dirty', mtype, field_count))
                    else:
                        results.append((str(filepath), 'clean', mtype, 0))
                except Exception:
                    results.append((str(filepath), 'unsupported', None, 0))
            GLib.idle_add(self._show_audit_results, results, folder, False)

        threading.Thread(target=worker, daemon=True).start()

    def _show_audit_results(self, results, folder, was_cancelled=False):
        self.audit_spinner.stop()
        self.audit_spinner.set_visible(False)
        self.audit_progress_label.set_visible(False)
        self.btn_audit_cancel.set_visible(False)
        self.audit_results = results

        if was_cancelled:
            self._show_toast('Scan cancelled \u2014 showing partial results')

        dirty = [r for r in results if r[1] == 'dirty']
        clean = [r for r in results if r[1] == 'clean']
        unsupported = [r for r in results if r[1] == 'unsupported']

        # Summary stats
        for count, label, color in [
            (len(results), 'Total', '#818cf8'),
            (len(dirty), 'With Metadata', '#f472b6'),
            (len(clean), 'Clean', '#34d399'),
            (len(unsupported), 'Unsupported', '#c4c4f0'),
        ]:
            stat = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, halign=Gtk.Align.CENTER, spacing=2)
            num = Gtk.Label()
            num.set_markup(f'<span foreground="{color}" weight="heavy" size="x-large">{count}</span>')
            stat.append(num)
            lbl = Gtk.Label(label=label)
            lbl.add_css_class('stat-label')
            stat.append(lbl)
            self.audit_summary.append(stat)

        # Sort: dirty first, then clean, then unsupported
        sorted_results = sorted(results, key=lambda r: {'dirty': 0, 'clean': 1, 'unsupported': 2}[r[1]])

        base = Path(folder)
        for filepath, status, mtype, count in sorted_results:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=10)
            row.add_css_class('audit-row')

            # Status icon
            icon = Gtk.Label()
            if status == 'dirty':
                icon.set_markup('<span foreground="#f472b6">\u26a0</span>')
            elif status == 'clean':
                icon.set_markup('<span foreground="#34d399">\u2714</span>')
            else:
                icon.set_markup('<span foreground="#555">\u2014</span>')
            row.append(icon)

            # File info
            info = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=1, hexpand=True)
            try:
                rel = str(Path(filepath).relative_to(base))
            except ValueError:
                rel = filepath
            name_lbl = Gtk.Label(label=rel, halign=Gtk.Align.START)
            name_lbl.add_css_class('file-item-name')
            name_lbl.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
            info.append(name_lbl)
            row.append(info)

            # Status / count
            tag = Gtk.Label(halign=Gtk.Align.END)
            if status == 'dirty':
                tag.set_label(f'{count} fields')
                tag.add_css_class('audit-dirty')
            elif status == 'clean':
                tag.set_label('Clean')
                tag.add_css_class('audit-clean')
            else:
                tag.set_label('Unsupported')
                tag.add_css_class('audit-unsupported')
            row.append(tag)

            # Double-click to view metadata (only for supported files)
            if status != 'unsupported':
                gesture = Gtk.GestureClick(button=1)
                gesture.connect('released', self._on_audit_row_double_click, filepath)
                row.add_controller(gesture)

            self.audit_list.append(row)

        self.btn_audit_export.set_sensitive(True)
        self.btn_audit_rescan.set_sensitive(True)

        # Enable batch strip if there are dirty files
        self._audit_dirty_files = [r[0] for r in dirty]
        self.btn_audit_strip.set_sensitive(len(dirty) > 0)

    def _on_audit_rescan(self):
        folder = self.audit_folder_label.get_label()
        if folder:
            self._run_audit(folder)

    def _on_audit_row_double_click(self, gesture, n_press, x, y, filepath):
        if n_press == 2:
            self.current_file = filepath
            self._load_metadata(filepath)

    def _on_audit_export(self):
        if not self.audit_results:
            return
        dialog = Gtk.FileDialog()
        dialog.set_title('Save audit report as JSON')
        self._set_dialog_initial_folder(dialog)
        dialog.set_initial_name('audit_report.json')
        dialog.save(self.win, None, self._on_audit_export_save)

    def _on_audit_export_save(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        self._remember_directory(path)
        report = {
            'folder': self.audit_folder_label.get_label(),
            'files': [
                {'path': r[0], 'status': r[1], 'mimetype': r[2], 'field_count': r[3]}
                for r in self.audit_results
            ],
        }
        try:
            with open(path, 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self._show_toast('Audit report exported')
        except Exception as e:
            self._show_toast(f'Export failed: {e}')

    # ---- Batch Strip from Audit ----

    def _on_audit_batch_strip(self):
        if not self._audit_dirty_files:
            return
        count = len(self._audit_dirty_files)
        dialog = Adw.AlertDialog(
            heading='Strip all dirty files?',
            body=f'This will permanently remove all metadata from {count} file(s). This cannot be undone.',
        )
        dialog.add_response('cancel', 'Cancel')
        dialog.add_response('strip', 'Strip All')
        dialog.set_response_appearance('strip', Adw.ResponseAppearance.DESTRUCTIVE)
        dialog.set_default_response('cancel')
        dialog.set_close_response('cancel')
        dialog.choose(self.win, None, self._on_audit_batch_strip_response)

    def _on_audit_batch_strip_response(self, dialog, result):
        try:
            response = dialog.choose_finish(result)
        except GLib.Error:
            return
        if response != 'strip':
            return

        files = list(self._audit_dirty_files)

        def worker():
            results = []
            for filepath in files:
                error = self._validate_file(filepath, need_write=True)
                if error:
                    results.append((False, filepath, error))
                    continue
                try:
                    parser, mtype = parser_factory.get_parser(filepath)
                    if parser is None:
                        results.append((False, filepath, f'Unsupported: {mtype or "unknown"}'))
                        continue
                    success = parser.remove_all()
                    if success:
                        shutil.move(parser.output_filename, filepath)
                        results.append((True, filepath, 'All metadata removed'))
                    else:
                        results.append((False, filepath, 'mat2 failed to clean'))
                except Exception as e:
                    results.append((False, filepath, str(e)))
            GLib.idle_add(self._show_strip_results, results)

        threading.Thread(target=worker, daemon=True).start()

    # ---- Compare Metadata ----

    def _on_compare_metadata(self):
        self.compare_file_a = None
        self.compare_file_b = None
        dialog = Gtk.FileDialog()
        dialog.set_title('Select first file')
        self._set_dialog_initial_folder(dialog)
        dialog.open(self.win, None, self._on_compare_file_a_chosen)

    def _on_compare_file_a_chosen(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        self.compare_file_a = gfile.get_path()
        self._remember_directory(self.compare_file_a)
        dialog2 = Gtk.FileDialog()
        dialog2.set_title('Select second file')
        self._set_dialog_initial_folder(dialog2)
        dialog2.open(self.win, None, self._on_compare_file_b_chosen)

    def _on_compare_file_b_chosen(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        self.compare_file_b = gfile.get_path()
        self._remember_directory(self.compare_file_b)
        self._navigate('compare')
        self._run_compare()

    def _build_compare_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # File headers
        self.compare_header_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            margin_top=12, margin_bottom=8, margin_start=16, margin_end=16,
        )
        self.compare_label_a = Gtk.Label(label='', halign=Gtk.Align.START, hexpand=True)
        self.compare_label_a.add_css_class('heading')
        self.compare_label_a.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.compare_header_box.append(self.compare_label_a)

        vs_label = Gtk.Label(label='vs')
        vs_label.add_css_class('dim-label')
        self.compare_header_box.append(vs_label)

        self.compare_label_b = Gtk.Label(label='', halign=Gtk.Align.END, hexpand=True)
        self.compare_label_b.add_css_class('heading')
        self.compare_label_b.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        self.compare_header_box.append(self.compare_label_b)

        page.append(self.compare_header_box)
        page.append(Gtk.Separator())

        # Column header row (Field | file_a | file_b)
        self.compare_col_header = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8, homogeneous=True,
            margin_top=8, margin_bottom=4, margin_start=16, margin_end=16,
        )
        self._col_hdr_field = Gtk.Label(label='Field', halign=Gtk.Align.FILL, hexpand=True)
        self._col_hdr_field.set_xalign(0)
        self._col_hdr_field.add_css_class('dim-label')
        self._col_hdr_a = Gtk.Label(label='', halign=Gtk.Align.FILL, hexpand=True)
        self._col_hdr_a.set_xalign(0)
        self._col_hdr_a.add_css_class('dim-label')
        self._col_hdr_b = Gtk.Label(label='', halign=Gtk.Align.FILL, hexpand=True)
        self._col_hdr_b.set_xalign(0)
        self._col_hdr_b.add_css_class('dim-label')
        self.compare_col_header.append(self._col_hdr_field)
        self.compare_col_header.append(self._col_hdr_a)
        self.compare_col_header.append(self._col_hdr_b)
        page.append(self.compare_col_header)

        # Hide Identical toggle
        toggle_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.CENTER,
            margin_top=4, margin_bottom=4,
        )
        self.btn_hide_same = Gtk.ToggleButton(label='Hide Identical')
        self.btn_hide_same.add_css_class('pill')
        self.btn_hide_same.set_active(False)
        self.btn_hide_same.connect('toggled', self._on_toggle_hide_same)
        toggle_row.append(self.btn_hide_same)
        page.append(toggle_row)

        # Spinner
        self.compare_spinner = Gtk.Spinner(halign=Gtk.Align.CENTER, margin_top=8)
        self.compare_spinner.set_size_request(32, 32)
        self.compare_spinner.set_visible(False)
        page.append(self.compare_spinner)

        # Scrollable diff list
        scrolled = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            margin_top=4, margin_bottom=8, margin_start=16, margin_end=16,
        )
        self.compare_list = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4,
            margin_top=4, margin_bottom=4, margin_start=4, margin_end=4,
        )
        scrolled.set_child(self.compare_list)
        page.append(scrolled)

        # Buttons
        btn_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.CENTER,
            spacing=12,
            margin_bottom=16,
        )
        btn_home = Gtk.Button(label='Back to Home')
        btn_home.add_css_class('suggested-action')
        btn_home.add_css_class('pill')
        btn_home.connect('clicked', lambda _b: self._go_home())
        btn_row.append(btn_home)

        self.btn_compare_export = Gtk.Button(label='Export Diff')
        self.btn_compare_export.add_css_class('pill')
        self.btn_compare_export.set_sensitive(False)
        self.btn_compare_export.connect('clicked', lambda _b: self._on_compare_export())
        btn_row.append(self.btn_compare_export)

        page.append(btn_row)
        return page

    def _on_toggle_hide_same(self, btn):
        hide = btn.get_active()
        for row, status in self._compare_rows:
            if status == 'same':
                row.set_visible(not hide)

    def _run_compare(self):
        while child := self.compare_list.get_first_child():
            self.compare_list.remove(child)

        name_a = Path(self.compare_file_a).name
        name_b = Path(self.compare_file_b).name
        self.compare_label_a.set_label(name_a)
        self.compare_label_b.set_label(name_b)
        self._col_hdr_a.set_label(name_a)
        self._col_hdr_b.set_label(name_b)
        self.compare_spinner.set_visible(True)
        self.compare_spinner.start()
        self.btn_compare_export.set_sensitive(False)
        self.btn_hide_same.set_active(False)
        self.compare_diff_data = {}
        self._compare_rows = []

        def _get_flat_meta(filepath):
            parser, mtype = parser_factory.get_parser(filepath)
            if parser is None:
                return {}
            meta = parser.get_meta()
            flat = {}
            for k, v in meta.items():
                if isinstance(v, dict):
                    for sk, sv in v.items():
                        flat[f'{k}.{sk}'] = str(sv)
                else:
                    flat[k] = str(v)
            return flat

        def worker():
            try:
                meta_a = _get_flat_meta(self.compare_file_a)
                meta_b = _get_flat_meta(self.compare_file_b)
                GLib.idle_add(self._show_compare, meta_a, meta_b)
            except Exception as e:
                GLib.idle_add(self._show_compare_error, str(e))

        threading.Thread(target=worker, daemon=True).start()

    def _show_compare_error(self, msg):
        self.compare_spinner.stop()
        self.compare_spinner.set_visible(False)
        lbl = Gtk.Label(label=msg)
        lbl.add_css_class('error')
        self.compare_list.append(lbl)

    def _show_compare(self, meta_a, meta_b):
        self.compare_spinner.stop()
        self.compare_spinner.set_visible(False)

        all_keys = sorted(set(meta_a.keys()) | set(meta_b.keys()))
        diff_data = []

        for key in all_keys:
            in_a = key in meta_a
            in_b = key in meta_b
            val_a = meta_a.get(key, '')
            val_b = meta_b.get(key, '')

            if in_a and in_b and val_a == val_b:
                status = 'same'
            elif in_a and in_b:
                status = 'diff'
            elif in_a:
                status = 'only_a'
            else:
                status = 'only_b'

            diff_data.append((key, val_a, val_b, status))

        self.compare_diff_data = diff_data

        # Sort: diff first, only_a, only_b, same last
        order = {'diff': 0, 'only_a': 1, 'only_b': 2, 'same': 3}
        diff_data.sort(key=lambda x: order[x[3]])

        self._compare_rows = []

        for key, val_a, val_b, status in diff_data:
            row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=8, homogeneous=True)
            row.add_css_class('meta-row')

            # Column 1: field name
            key_lbl = Gtk.Label(label=key, halign=Gtk.Align.FILL, hexpand=True)
            key_lbl.set_wrap(True)
            key_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            key_lbl.set_xalign(0)
            key_lbl.add_css_class('meta-key')
            row.append(key_lbl)

            # Column 2: value from image 1
            a_lbl = Gtk.Label(label=val_a or '\u2014', halign=Gtk.Align.FILL, hexpand=True)
            a_lbl.set_wrap(True)
            a_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            a_lbl.set_xalign(0)
            if status == 'same':
                a_lbl.add_css_class('meta-value')
            elif status == 'diff':
                a_lbl.add_css_class('meta-value')
            else:
                a_lbl.add_css_class('dim-label')
            row.append(a_lbl)

            # Column 3: value from image 2
            b_lbl = Gtk.Label(label=val_b or '\u2014', halign=Gtk.Align.FILL, hexpand=True)
            b_lbl.set_wrap(True)
            b_lbl.set_wrap_mode(Pango.WrapMode.WORD_CHAR)
            b_lbl.set_xalign(0)
            if status == 'same':
                b_lbl.add_css_class('meta-value')
            elif status == 'diff':
                b_lbl.add_css_class('compare-diff')
            else:
                b_lbl.add_css_class('dim-label')
            row.append(b_lbl)

            self.compare_list.append(row)
            self._compare_rows.append((row, status))

        self.btn_compare_export.set_sensitive(True)

    def _on_compare_export(self):
        if not self.compare_diff_data:
            return
        dialog = Gtk.FileDialog()
        dialog.set_title('Save comparison as JSON')
        self._set_dialog_initial_folder(dialog)
        dialog.set_initial_name('metadata_diff.json')
        dialog.save(self.win, None, self._on_compare_export_save)

    def _on_compare_export_save(self, dialog, result):
        try:
            gfile = dialog.save_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        self._remember_directory(path)
        report = {
            'file_a': self.compare_file_a,
            'file_b': self.compare_file_b,
            'diff': [
                {'key': k, 'value_a': a, 'value_b': b, 'status': s}
                for k, a, b, s in self.compare_diff_data
            ],
        }
        try:
            with open(path, 'w') as f:
                json.dump(report, f, indent=2, ensure_ascii=False)
            self._show_toast('Comparison exported')
        except Exception as e:
            self._show_toast(f'Export failed: {e}')

    # ---- Location Finder ----

    def _build_location_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        # File info bar
        self.loc_file_info = Gtk.Label(
            label='',
            halign=Gtk.Align.START,
            margin_top=12, margin_bottom=8, margin_start=20, margin_end=20,
        )
        self.loc_file_info.add_css_class('heading')
        self.loc_file_info.set_ellipsize(Pango.EllipsizeMode.MIDDLE)
        page.append(self.loc_file_info)

        page.append(Gtk.Separator())

        # Spinner
        self.loc_spinner = Gtk.Spinner(halign=Gtk.Align.CENTER, valign=Gtk.Align.CENTER)
        self.loc_spinner.set_size_request(32, 32)
        self.loc_spinner.set_visible(False)
        page.append(self.loc_spinner)

        # Center content area
        center_box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=16,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            vexpand=True,
            margin_start=24, margin_end=24,
        )

        self.loc_icon = Gtk.Label()
        self.loc_icon.set_markup('<span size="30000">\U0001f4cd</span>')
        center_box.append(self.loc_icon)

        self.loc_result_label = Gtk.Label(label='')
        self.loc_result_label.add_css_class('title-2')
        self.loc_result_label.set_wrap(True)
        self.loc_result_label.set_max_width_chars(50)
        self.loc_result_label.set_justify(Gtk.Justification.CENTER)
        center_box.append(self.loc_result_label)

        self.loc_address_label = Gtk.Label(label='')
        self.loc_address_label.set_wrap(True)
        self.loc_address_label.set_max_width_chars(60)
        self.loc_address_label.set_justify(Gtk.Justification.CENTER)
        self.loc_address_label.set_selectable(True)
        center_box.append(self.loc_address_label)

        self.loc_address_en_label = Gtk.Label(label='')
        self.loc_address_en_label.set_wrap(True)
        self.loc_address_en_label.set_max_width_chars(60)
        self.loc_address_en_label.set_justify(Gtk.Justification.CENTER)
        self.loc_address_en_label.set_selectable(True)
        self.loc_address_en_label.set_margin_top(4)
        center_box.append(self.loc_address_en_label)

        self.loc_coords_label = Gtk.Label(label='')
        self.loc_coords_label.add_css_class('dim-label')
        self.loc_coords_label.set_selectable(True)
        center_box.append(self.loc_coords_label)

        page.append(center_box)

        # Bottom buttons
        btn_box = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12,
            halign=Gtk.Align.CENTER,
            margin_bottom=16, margin_start=20, margin_end=20,
        )

        self.loc_btn_strip = Gtk.Button(label='Strip Metadata')
        self.loc_btn_strip.add_css_class('destructive-action')
        self.loc_btn_strip.add_css_class('pill')
        self.loc_btn_strip.set_visible(False)
        self.loc_btn_strip.connect('clicked', lambda _b: self._on_location_strip())
        btn_box.append(self.loc_btn_strip)

        self.loc_btn_home = Gtk.Button(label='Back to Home')
        self.loc_btn_home.add_css_class('pill')
        self.loc_btn_home.set_visible(False)
        self.loc_btn_home.connect('clicked', lambda _b: self._go_home())
        btn_box.append(self.loc_btn_home)

        page.append(btn_box)

        return page

    def _on_location_finder(self):
        dialog = Gtk.FileDialog()
        dialog.set_title('Select an image')
        self._set_dialog_initial_folder(dialog)
        img_filter = Gtk.FileFilter()
        img_filter.set_name('Images')
        for pattern in ('*.jpg', '*.jpeg', '*.png', '*.tiff', '*.tif',
                        '*.heic', '*.heif', '*.webp', '*.bmp', '*.gif'):
            img_filter.add_pattern(pattern)
            img_filter.add_pattern(pattern.upper())
        filters = Gio.ListStore.new(Gtk.FileFilter)
        filters.append(img_filter)
        dialog.set_filters(filters)
        dialog.set_default_filter(img_filter)
        dialog.open(self.win, None, self._on_location_file_chosen)

    def _on_location_file_chosen(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        filepath = gfile.get_path()
        if not filepath:
            return
        self._remember_directory(filepath)
        self._location_file = filepath
        self.loc_file_info.set_label(Path(filepath).name)

        # Reset UI
        self.loc_icon.set_markup('<span size="30000">\U0001f4cd</span>')
        self.loc_result_label.set_label('')
        self.loc_address_label.set_label('')
        self.loc_address_en_label.set_label('')
        self.loc_coords_label.set_label('')
        self.loc_btn_strip.set_visible(False)
        self.loc_btn_home.set_visible(False)
        self.loc_spinner.set_visible(True)
        self.loc_spinner.start()
        self._navigate('location')

        threading.Thread(target=self._location_worker, args=(filepath,), daemon=True).start()

    def _location_worker(self, filepath):
        """Extract GPS from exiftool and reverse-geocode via Nominatim."""
        try:
            proc = subprocess.run(
                ['exiftool', '-json', '-GPS:GPSLatitude', '-GPS:GPSLongitude',
                 '-GPS:GPSLatitudeRef', '-GPS:GPSLongitudeRef', filepath],
                capture_output=True, text=True, timeout=10,
            )
            data = json.loads(proc.stdout)
            if not data:
                GLib.idle_add(self._show_location_result, None, None, None, None)
                return

            info = data[0]
            lat_str = info.get('GPSLatitude', '')
            lon_str = info.get('GPSLongitude', '')

            if not lat_str or not lon_str:
                GLib.idle_add(self._show_location_result, None, None, None, None)
                return

            lat = self._dms_to_decimal(lat_str, info.get('GPSLatitudeRef', 'N'))
            lon = self._dms_to_decimal(lon_str, info.get('GPSLongitudeRef', 'E'))

            if lat is None or lon is None:
                GLib.idle_add(self._show_location_result, None, None, None, None)
                return

            # Reverse geocode — local language
            base_url = (
                f'https://nominatim.openstreetmap.org/reverse'
                f'?format=jsonv2&lat={lat}&lon={lon}&zoom=18&addressdetails=1'
            )
            headers = {
                'User-Agent': 'Pikapika/1.0 (metadata viewer)',
                'Accept': 'application/json',
            }
            req = urllib.request.Request(base_url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                geo_local = json.loads(resp.read().decode())
            address_local = geo_local.get('display_name', f'{lat}, {lon}')

            # Reverse geocode — English
            url_en = base_url + '&accept-language=en'
            req_en = urllib.request.Request(url_en, headers=headers)
            with urllib.request.urlopen(req_en, timeout=10) as resp:
                geo_en = json.loads(resp.read().decode())
            address_en = geo_en.get('display_name', '')

            # If both are identical, no need to show twice
            if address_en == address_local:
                address_en = ''

            GLib.idle_add(self._show_location_result, lat, lon, address_local, address_en)

        except Exception as e:
            GLib.idle_add(self._show_location_error, str(e))

    @staticmethod
    def _dms_to_decimal(dms_str, ref):
        """Convert exiftool DMS string like '35 deg 42\\' 28.21\"' to decimal."""
        import re
        # Try parsing as a plain float first (exiftool sometimes returns decimal)
        try:
            val = float(dms_str)
            if ref in ('S', 'W'):
                val = -val
            return val
        except (ValueError, TypeError):
            pass
        # Parse DMS: e.g. "35 deg 42' 28.21\""
        m = re.match(
            r"(\d+)\s*deg\s*(\d+)'\s*([\d.]+)\"?",
            dms_str.strip(),
        )
        if not m:
            return None
        d, mins, secs = float(m.group(1)), float(m.group(2)), float(m.group(3))
        val = d + mins / 60 + secs / 3600
        if ref in ('S', 'W'):
            val = -val
        return val

    def _show_location_result(self, lat, lon, address, address_en):
        self.loc_spinner.stop()
        self.loc_spinner.set_visible(False)

        if lat is None:
            self.loc_icon.set_markup('<span size="30000" foreground="#f87171">\u2718</span>')
            self.loc_result_label.set_label('No GPS data was found in the image')
            self.loc_address_label.set_label('')
            self.loc_address_en_label.set_label('')
            self.loc_coords_label.set_label('')
            self.loc_btn_strip.set_visible(False)
            self.loc_btn_home.set_visible(True)
            return

        self.loc_icon.set_markup('<span size="30000" foreground="#34d399">\U0001f4cd</span>')
        self.loc_result_label.set_label('Photo location found')
        self.loc_address_label.set_label(address)
        self.loc_address_en_label.set_label(address_en or '')
        self.loc_coords_label.set_label(f'{lat:.6f}, {lon:.6f}')
        self.loc_btn_strip.set_visible(True)
        self.loc_btn_home.set_visible(True)

    def _show_location_error(self, message):
        self.loc_spinner.stop()
        self.loc_spinner.set_visible(False)
        self.loc_icon.set_markup('<span size="30000" foreground="#f87171">\u2718</span>')
        self.loc_result_label.set_label('Error')
        self.loc_address_label.set_label(message)
        self.loc_coords_label.set_label('')
        self.loc_btn_strip.set_visible(False)
        self.loc_btn_home.set_visible(True)

    def _on_location_strip(self):
        filepath = getattr(self, '_location_file', None)
        if not filepath:
            return
        self.strip_files = [filepath]
        self._populate_strip_file_list()
        self._navigate('strip-confirm')

    # ---- About Metadata ----

    _ABOUT_METADATA_SECTIONS = [
        ('What is Metadata?',
         'Every file you create carries invisible extra information alongside its '
         'actual content. This is metadata \u2014 data about data. You can\'t see it by '
         'opening the file normally, but it\'s there, and anyone who receives the '
         'file can read it.'),
        ('Photos and Images',
         'Your phone or camera records things like GPS coordinates (the exact '
         'location where the photo was taken), date and time down to the second '
         'including timezone, device details such as camera make, model and '
         'sometimes the serial number of your specific device, which software '
         'was used to edit the photo, and embedded thumbnails \u2014 a small preview '
         'image baked into the file, which some editing tools forget to update '
         'when you crop or redact the main image.'),
        ('Documents',
         'PDFs, Word files and spreadsheets can include your author name (often '
         'pulled automatically from your computer\'s user account), your organisation '
         'or workplace name, revision history showing how many times the file was '
         'edited and total editing time, the hostname of the computer it was created '
         'on, and traces of comments and tracked changes even after you\'ve accepted them.'),
        ('Audio and Video',
         'Audio and video files may contain recording device info, GPS data, '
         'software details, and duration and bitrate information.'),
        ('Why Does This Matter?',
         'Most of the time, metadata is harmless. But when you share files publicly '
         'or with people you don\'t fully trust, it can reveal more than you intended. '
         'A photo posted online might tell someone exactly where you live. A PDF sent '
         'to a client might expose your personal name or an internal username. A '
         'cropped image might still carry the original dimensions, hinting at what '
         'was removed.\n\n'
         'You don\'t need to be paranoid about metadata \u2014 but it\'s worth knowing it '
         'exists, and having the option to remove it before sharing.'),
        ('How Pikapika Helps',
         'View Metadata \u2014 Open any supported file and see every metadata field it '
         'contains. Select individual fields and strip only those, or export the '
         'full list to JSON.\n\n'
         'Strip Metadata \u2014 Select one or more files and remove all metadata at once.\n\n'
         'Folder Audit \u2014 Scan a folder and see which files contain metadata and how '
         'many fields each has.\n\n'
         'Compare \u2014 Side-by-side metadata diff of two files, colour-coded to show '
         'what\'s different.\n\n'
         'Location Finder \u2014 Check a photo for embedded GPS data and see the address '
         'where it was taken.\n\n'
         '(In case you were wondering\u2026 pikapika is Japanese for squeaky clean.)'),
    ]

    def _build_about_metadata_page(self):
        page = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=0)

        heading = Gtk.Label(
            label='About Metadata',
            halign=Gtk.Align.START,
            margin_top=12, margin_bottom=8, margin_start=20, margin_end=20,
        )
        heading.add_css_class('heading')
        page.append(heading)

        page.append(Gtk.Separator())

        scrolled = Gtk.ScrolledWindow(
            vexpand=True,
            hscrollbar_policy=Gtk.PolicyType.NEVER,
            margin_top=8, margin_bottom=8, margin_start=16, margin_end=16,
        )
        content = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=12,
            margin_top=8, margin_bottom=8, margin_start=8, margin_end=8,
        )

        for title, body in self._ABOUT_METADATA_SECTIONS:
            section = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=6)

            title_label = Gtk.Label(label=title, halign=Gtk.Align.START)
            title_label.add_css_class('title-4')
            section.append(title_label)

            body_label = Gtk.Label(
                label=body,
                halign=Gtk.Align.START,
                wrap=True,
                max_width_chars=80,
                xalign=0,
            )
            section.append(body_label)

            content.append(section)

        scrolled.set_child(content)
        page.append(scrolled)

        return page

    def _on_about_metadata(self):
        self._navigate('about-metadata')


def main():
    app = PikapikaApp()
    app.run(None)


if __name__ == '__main__':
    main()
