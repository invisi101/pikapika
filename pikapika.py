#!/usr/bin/env python3
"""Pikapika — Metadata Viewer & Stripper."""

import os
import shutil
import subprocess
import threading
from pathlib import Path

import gi
gi.require_version('Gtk', '4.0')
gi.require_version('Adw', '1')
from gi.repository import Gtk, Adw, Gio, GLib, Pango, PangoCairo

from libmat2 import parser_factory


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
    padding: 32px 24px;
    transition: all 200ms ease;
    min-width: 220px;
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
    font-size: 48px;
    margin-bottom: 8px;
}

.mode-card-title {
    color: #e0e0ff;
    font-weight: 700;
    font-size: 16px;
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
        self.meta_checks = {}  # key -> CheckButton
        self.strip_files = []  # list of file paths for bulk strip

        # Header bar
        self.header = Adw.HeaderBar()
        self.title_label = Gtk.Label(label='Pikapika', css_classes=['title'])
        self.header.set_title_widget(self.title_label)

        self.btn_back = Gtk.Button(icon_name='go-previous-symbolic')
        self.btn_back.connect('clicked', lambda _b: self._go_home())
        self.btn_back.set_visible(False)
        self.header.pack_start(self.btn_back)

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

        vbox = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        vbox.append(self.header)
        vbox.append(self.stack)
        self.win.set_content(vbox)

        self.stack.set_visible_child_name('welcome')
        self.win.present()

    # ---- CSS ----

    def _load_css(self):
        from gi.repository import Gdk
        css_provider = Gtk.CssProvider()
        css_provider.load_from_data(CUSTOM_CSS.encode('utf-8'))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            css_provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    # ---- Navigation ----

    def _navigate(self, page_name):
        is_home = page_name == 'welcome'
        self.btn_back.set_visible(not is_home)
        self.title_label.set_label('Pikapika' if is_home else
                                   {'view-metadata': 'View Metadata',
                                    'view-result': 'Result',
                                    'strip-confirm': 'Strip Metadata',
                                    'strip-result': 'Result'}.get(page_name, 'Pikapika'))
        self.stack.set_visible_child_name(page_name)

    def _go_home(self):
        self._navigate('welcome')

    # ---- Welcome Page ----

    def _build_welcome_page(self):
        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            spacing=32,
        )

        heading = Gtk.Label()
        heading.set_markup(
            '<span font_family="Vegan Style Personal Use" size="xxx-large">Pikapika</span>'
        )
        heading.add_css_class('title-1')
        page.append(heading)

        subtitle = Gtk.Label(label='What would you like to do?')
        subtitle.add_css_class('dim-label')
        page.append(subtitle)

        cards_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            halign=Gtk.Align.CENTER,
            spacing=24,
        )

        # View Metadata card
        view_card = Gtk.Button()
        view_card.add_css_class('mode-card')
        view_card.set_has_frame(False)
        view_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                           halign=Gtk.Align.CENTER)

        view_icon = Gtk.Label()
        view_icon.add_css_class('mode-card-icon')
        view_icon.set_markup('<span size="xx-large" weight="bold">\U0001f50d</span>')
        view_box.append(view_icon)

        view_title = Gtk.Label(label='View Metadata')
        view_title.add_css_class('mode-card-title')
        view_box.append(view_title)

        view_sub = Gtk.Label(label='Inspect and selectively strip metadata fields')
        view_sub.add_css_class('mode-card-subtitle')
        view_sub.set_wrap(True)
        view_sub.set_max_width_chars(25)
        view_sub.set_justify(Gtk.Justification.CENTER)
        view_box.append(view_sub)

        view_card.set_child(view_box)
        view_card.connect('clicked', lambda _b: self._on_view_metadata())
        cards_row.append(view_card)

        # Strip Metadata card
        strip_card = Gtk.Button()
        strip_card.add_css_class('mode-card')
        strip_card.set_has_frame(False)
        strip_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=8,
                            halign=Gtk.Align.CENTER)

        strip_icon = Gtk.Label()
        strip_icon.add_css_class('mode-card-icon')
        strip_icon.set_markup('<span size="xx-large" weight="bold">\u2702</span>')
        strip_box.append(strip_icon)

        strip_title = Gtk.Label(label='Strip Metadata')
        strip_title.add_css_class('mode-card-title')
        strip_box.append(strip_title)

        strip_sub = Gtk.Label(label='Remove all metadata from one or more files')
        strip_sub.add_css_class('mode-card-subtitle')
        strip_sub.set_wrap(True)
        strip_sub.set_max_width_chars(25)
        strip_sub.set_justify(Gtk.Justification.CENTER)
        strip_box.append(strip_sub)

        strip_card.set_child(strip_box)
        strip_card.connect('clicked', lambda _b: self._on_strip_metadata())
        cards_row.append(strip_card)

        page.append(cards_row)
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

        return page

    # ---- View Result Page ----

    def _build_view_result_page(self):
        page = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
            spacing=16,
        )

        self.view_result_icon = Gtk.Label()
        self.view_result_icon.set_markup('<span size="xxx-large">\u2714</span>')
        page.append(self.view_result_icon)

        self.view_result_label = Gtk.Label(label='')
        self.view_result_label.add_css_class('title-2')
        self.view_result_label.set_wrap(True)
        self.view_result_label.set_max_width_chars(45)
        self.view_result_label.set_justify(Gtk.Justification.CENTER)
        page.append(self.view_result_label)

        self.view_result_detail = Gtk.Label(label='')
        self.view_result_detail.add_css_class('dim-label')
        self.view_result_detail.set_wrap(True)
        self.view_result_detail.set_max_width_chars(50)
        self.view_result_detail.set_justify(Gtk.Justification.CENTER)
        page.append(self.view_result_detail)

        btn_home = Gtk.Button(label='Back to Home')
        btn_home.add_css_class('suggested-action')
        btn_home.add_css_class('pill')
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

    # ---- View Metadata Flow ----

    def _on_view_metadata(self):
        dialog = Gtk.FileDialog()
        dialog.set_title('Select a file to inspect')
        dialog.open(self.win, None, self._on_view_file_chosen)

    def _on_view_file_chosen(self, dialog, result):
        try:
            gfile = dialog.open_finish(result)
        except GLib.Error:
            return
        path = gfile.get_path()
        self.current_file = path
        self._load_metadata(path)

    def _load_metadata(self, filepath):
        self.view_file_info.set_label(Path(filepath).name)
        self.view_mime_label.set_label('')
        self._clear_meta_list()
        self.view_spinner.set_visible(True)
        self.view_spinner.start()
        self.view_status_label.set_visible(False)
        self.btn_strip_selected.set_sensitive(False)
        self.btn_select_all.set_sensitive(False)
        self.btn_deselect_all.set_sensitive(False)
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
            self.view_status_label.set_label('No metadata found')
            self.view_status_label.remove_css_class('error')
            self.view_status_label.add_css_class('dim-label')
            self.view_status_label.set_visible(True)
            return

        # Flatten nested dicts
        flat = {}
        for k, v in meta.items():
            if isinstance(v, dict):
                for sk, sv in v.items():
                    flat[f'{k}.{sk}'] = str(sv)
            else:
                flat[k] = str(v)

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

    def _toggle_all_checks(self, state):
        for check in self.meta_checks.values():
            check.set_active(state)

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
        has_exiftool = shutil.which('exiftool') is not None

        if not has_exiftool:
            self._offer_mat2_fallback()
            return

        def worker():
            try:
                # Build exiftool args to strip selected tags
                args = ['exiftool', '-overwrite_original']
                for key in selected:
                    # Normalize key: remove prefixes like "Exif." etc.
                    tag = key.split('.')[-1] if '.' in key else key
                    args.append(f'-{tag}=')
                args.append(filepath)

                proc = subprocess.run(args, capture_output=True, text=True, timeout=30)
                if proc.returncode == 0:
                    GLib.idle_add(self._show_view_result, True,
                                  f'Stripped {len(selected)} field(s)',
                                  Path(filepath).name)
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
                        GLib.idle_add(self._show_view_result, True, msg, Path(filepath).name)
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

    def _show_view_result(self, success, message, detail):
        if success:
            self.view_result_icon.set_markup('<span size="xxx-large" foreground="#34d399">\u2714</span>')
            self.view_result_label.set_label(message)
            self.view_result_label.remove_css_class('error')
            self.view_result_label.add_css_class('result-success')
        else:
            self.view_result_icon.set_markup('<span size="xxx-large" foreground="#f87171">\u2718</span>')
            self.view_result_label.set_label(message)
            self.view_result_label.remove_css_class('result-success')
            self.view_result_label.add_css_class('result-fail')
        self.view_result_detail.set_label(detail)
        self._navigate('view-result')

    # ---- Strip Metadata Flow ----

    def _on_strip_metadata(self):
        dialog = Gtk.FileDialog()
        dialog.set_title('Select files to strip')
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


def main():
    app = PikapikaApp()
    app.run(None)


if __name__ == '__main__':
    main()
