"""
Makerspace Controller - Kivy App for Raspberry Pi 5" Touchscreen
Reads from and writes to Google Sheets, which then triggers the LED matrix display.

SETUP:
  pip install kivy gspread google-auth

Place your Google service account JSON file in the same directory as this script
and update SERVICE_ACCOUNT_FILE and SHEET_ID below.

GOOGLE SHEET HOURS SETUP:
  - D8  → Session 1 hours  (e.g. "9:00-5:00")  ← add a Data Validation dropdown here
  - E8  → Session 2 hours  (e.g. "9:00-8:00")  ← add a Data Validation dropdown here

  To add dropdown presets in Google Sheets:
    1. Click cell D8 (or E8)
    2. Data → Data Validation → Add a rule
    3. Criteria: Dropdown (from a list)
    4. Enter your preset options, e.g:
         9:00-5:00, 9:00-8:00, 10:00-4:00, 12:00-6:00, CLOSED
    5. Save — staff can now click the cell and pick a preset time
"""

import gspread
from google.oauth2.service_account import Credentials
from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
import threading

# ─────────────────────────────────────────────
#  CONFIG — update these for your setup
# ─────────────────────────────────────────────
SERVICE_ACCOUNT_FILE = "service_account.json"
SHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"

# Google Sheet cell addresses (A1 notation)
# Adjust these to match your sheet layout exactly
CELL_MAP = {
    "drills":          "B3",
    "calipers":        "B4",
    "glue":            "B5",
    "printer_open":    "E3",
    "printer_queue":   "E4",
    "machine_shop":    "B7",   # Written/read as "OPEN" or "CLOSED"
    "machine_reopen":  "B8",   # e.g. "3PM TODAY" (read-only)
    "hours_session1":  "D8",   # Session 1 — set via dropdown in sheet
    "hours_session2":  "E8",   # Session 2 — set via dropdown in sheet
    "projects":        "B11",  # Pickup list string (read-only)
}

POLL_INTERVAL = 15  # seconds between auto-refresh from sheet

# ─────────────────────────────────────────────
#  COLORS  (matching your mockup palette)
# ─────────────────────────────────────────────
BG_COLOR    = (0.05, 0.05, 0.05, 1)
YELLOW_TILE = (0.99, 0.78, 0.28, 1)
BLUE_TILE   = (0.40, 0.75, 0.90, 1)
RED_TILE    = (0.92, 0.26, 0.26, 1)
GREEN_TILE  = (0.18, 0.85, 0.40, 1)
BROWN_TILE  = (0.60, 0.35, 0.05, 1)
CHIP_YELLOW = (0.99, 0.78, 0.10, 1)   # bright yellow chip
CHIP_DARK   = (0.42, 0.24, 0.03, 1)   # dark brown chip
BTN_YELLOW  = (0.55, 0.48, 0.30, 1)
BTN_BLUE    = (0.30, 0.55, 0.70, 1)
TEXT_DARK   = (0.10, 0.10, 0.10, 1)
TEXT_LIGHT  = (0.95, 0.95, 0.95, 1)


# ─────────────────────────────────────────────
#  GOOGLE SHEETS INTERFACE
# ─────────────────────────────────────────────
class SheetsClient:
    def __init__(self):
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(
            SERVICE_ACCOUNT_FILE, scopes=scopes
        )
        self.client = gspread.authorize(creds)
        self.sheet = self.client.open_by_key(SHEET_ID).sheet1

    def read_all(self):
        """Fetch all tracked cells in a single batch API call."""
        cells = list(CELL_MAP.values())
        result = self.sheet.batch_get(cells)
        data = {}
        for key, cell_result in zip(CELL_MAP.keys(), result):
            try:
                data[key] = cell_result[0][0]
            except (IndexError, TypeError):
                data[key] = ""
        return data

    def write_cell(self, cell_key, value):
        """Write a single value to the sheet by key."""
        self.sheet.update(CELL_MAP[cell_key], [[value]])


# ─────────────────────────────────────────────
#  BASE TILE
# ─────────────────────────────────────────────
class RoundedTile(FloatLayout):
    """Colored rounded-rectangle base tile."""

    def __init__(self, bg_color, radius=18, **kwargs):
        super().__init__(**kwargs)
        self.bg_color = bg_color
        self.radius = radius
        self.bind(pos=self._redraw, size=self._redraw)

    def _redraw(self, *args):
        self.canvas.before.clear()
        with self.canvas.before:
            Color(*self.bg_color)
            RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(self.radius)])

    def set_color(self, color):
        self.bg_color = color
        self._redraw()


# ─────────────────────────────────────────────
#  COUNTER TILE  (+/- buttons)
# ─────────────────────────────────────────────
class CounterTile(RoundedTile):
    """
    Tile with a title, large count number, and +/− buttons.
    Writes updated count to Google Sheet on every press.
    """

    def __init__(self, title, cell_key, bg_color, btn_color, sheets_ref, **kwargs):
        super().__init__(bg_color=bg_color, **kwargs)
        self.cell_key = cell_key
        self.sheets_ref = sheets_ref
        self.count = 0

        layout = BoxLayout(
            orientation="vertical",
            padding=dp(8),
            spacing=dp(4),
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )

        self.title_lbl = Label(
            text=title,
            font_size=dp(13),
            bold=True,
            color=TEXT_DARK,
            halign="center",
            valign="middle",
            size_hint=(1, 0.22),
        )
        self.title_lbl.bind(size=self.title_lbl.setter("text_size"))

        self.count_lbl = Label(
            text="–",
            font_size=dp(52),
            bold=True,
            color=TEXT_DARK,
            halign="center",
            valign="middle",
            size_hint=(1, 0.50),
        )
        self.count_lbl.bind(size=self.count_lbl.setter("text_size"))

        btn_row = BoxLayout(
            orientation="horizontal",
            spacing=dp(8),
            size_hint=(1, 0.28),
            padding=[dp(10), 0, dp(10), 0],
        )
        btn_row.add_widget(self._make_btn("−", btn_color, self._decrement))
        btn_row.add_widget(self._make_btn("+", btn_color, self._increment))

        layout.add_widget(self.title_lbl)
        layout.add_widget(self.count_lbl)
        layout.add_widget(btn_row)
        self.add_widget(layout)

    def _make_btn(self, text, color, callback):
        btn = Button(
            text=text,
            font_size=dp(20),
            bold=True,
            color=TEXT_DARK,
            background_color=(0, 0, 0, 0),
            background_normal="",
        )
        with btn.canvas.before:
            Color(*color)
            rr = RoundedRectangle(pos=btn.pos, size=btn.size, radius=[dp(8)])
        btn.bind(
            pos=lambda i, v: setattr(rr, "pos", i.pos),
            size=lambda i, v: setattr(rr, "size", i.size),
        )
        btn.bind(on_press=callback)
        return btn

    def set_value(self, val):
        try:
            self.count = int(val)
        except (ValueError, TypeError):
            self.count = 0
        self.count_lbl.text = str(self.count)

    def _increment(self, *args):
        self.count += 1
        self.count_lbl.text = str(self.count)
        self._push()

    def _decrement(self, *args):
        if self.count > 0:
            self.count -= 1
            self.count_lbl.text = str(self.count)
            self._push()

    def _push(self):
        key, val = self.cell_key, self.count
        threading.Thread(
            target=self.sheets_ref.write_cell,
            args=(key, val),
            daemon=True,
        ).start()


# ─────────────────────────────────────────────
#  MACHINE SHOP TILE  (tap to toggle)
# ─────────────────────────────────────────────
class MachineShopTile(RoundedTile):
    """Tap anywhere on the tile to toggle between OPEN (green) and CLOSED (red)."""

    def __init__(self, sheets_ref, **kwargs):
        super().__init__(bg_color=RED_TILE, **kwargs)
        self.sheets_ref = sheets_ref
        self.is_open = False

        layout = BoxLayout(
            orientation="vertical",
            padding=dp(10),
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )

        self.header_lbl = Label(
            text="Machine\nShop",
            font_size=dp(13),
            bold=True,
            color=TEXT_DARK,
            halign="center",
            valign="middle",
            size_hint=(1, 0.35),
        )
        self.header_lbl.bind(size=self.header_lbl.setter("text_size"))

        self.status_lbl = Label(
            text="CLOSED",
            font_size=dp(28),
            bold=True,
            color=TEXT_DARK,
            halign="center",
            valign="middle",
            size_hint=(1, 0.65),
        )
        self.status_lbl.bind(size=self.status_lbl.setter("text_size"))

        layout.add_widget(self.header_lbl)
        layout.add_widget(self.status_lbl)
        self.add_widget(layout)

        # Transparent full-tile button to capture taps
        touch_btn = Button(
            background_color=(0, 0, 0, 0),
            background_normal="",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )
        touch_btn.bind(on_press=self._toggle)
        self.add_widget(touch_btn)

    def set_value(self, val):
        self.is_open = str(val).strip().upper() == "OPEN"
        self._apply()

    def _toggle(self, *args):
        self.is_open = not self.is_open
        self._apply()
        new_val = "OPEN" if self.is_open else "CLOSED"
        threading.Thread(
            target=self.sheets_ref.write_cell,
            args=("machine_shop", new_val),
            daemon=True,
        ).start()

    def _apply(self):
        self.set_color(GREEN_TILE if self.is_open else RED_TILE)
        self.status_lbl.text = "OPEN" if self.is_open else "CLOSED"


# ─────────────────────────────────────────────
#  HOURS CHIP  (one rounded chip inside HoursTile)
# ─────────────────────────────────────────────
class HoursChip(FloatLayout):
    """Single rounded chip showing one session's hours."""

    def __init__(self, chip_color, **kwargs):
        super().__init__(**kwargs)
        with self.canvas.before:
            self._color_inst = Color(*chip_color)
            self._rr = RoundedRectangle(pos=self.pos, size=self.size, radius=[dp(10)])
        self.bind(
            pos=lambda i, v: setattr(self._rr, "pos", i.pos),
            size=lambda i, v: setattr(self._rr, "size", i.size),
        )
        self.label = Label(
            text="–",
            font_size=dp(15),
            bold=True,
            color=TEXT_DARK,
            halign="center",
            valign="middle",
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )
        self.label.bind(size=self.label.setter("text_size"))
        self.add_widget(self.label)

    def set_text(self, text):
        self.label.text = str(text) if text else "–"


# ─────────────────────────────────────────────
#  HOURS TILE  (two chips, read-only from sheet)
# ─────────────────────────────────────────────
class HoursTile(RoundedTile):
    """
    Brown tile showing today's hours as two side-by-side chips.

    chip1 (yellow) ← hours_session1 cell (D8) — set via sheet dropdown
    chip2 (dark)   ← hours_session2 cell (E8) — set via sheet dropdown

    Both chips are READ-ONLY on the controller. Staff update them by
    selecting from the dropdown list in Google Sheets.
    """

    def __init__(self, **kwargs):
        super().__init__(bg_color=BROWN_TILE, **kwargs)

        layout = BoxLayout(
            orientation="vertical",
            padding=[dp(10), dp(8), dp(10), dp(8)],
            spacing=dp(6),
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )

        header = Label(
            text="Today's Hours",
            font_size=dp(13),
            bold=True,
            color=TEXT_LIGHT,
            halign="center",
            valign="middle",
            size_hint=(1, 0.28),
        )
        header.bind(size=header.setter("text_size"))

        chips_row = BoxLayout(
            orientation="horizontal",
            spacing=dp(10),
            size_hint=(1, 0.72),
        )

        self.chip1 = HoursChip(chip_color=CHIP_YELLOW, size_hint=(1, 1))
        self.chip2 = HoursChip(chip_color=CHIP_DARK,   size_hint=(1, 1))

        chips_row.add_widget(self.chip1)
        chips_row.add_widget(self.chip2)

        layout.add_widget(header)
        layout.add_widget(chips_row)
        self.add_widget(layout)

    def set_value(self, session1, session2):
        """Update both chips from the latest sheet data."""
        self.chip1.set_text(session1)
        self.chip2.set_text(session2)


# ─────────────────────────────────────────────
#  PROJECTS BAR  (read-only)
# ─────────────────────────────────────────────
class ProjectsTile(RoundedTile):
    """Full-width bar showing projects ready for pickup."""

    def __init__(self, **kwargs):
        super().__init__(bg_color=(0.15, 0.15, 0.15, 1), radius=12, **kwargs)

        layout = BoxLayout(
            orientation="vertical",
            padding=dp(8),
            spacing=dp(2),
            size_hint=(1, 1),
            pos_hint={"x": 0, "y": 0},
        )

        header = Label(
            text="PROJECTS READY FOR PICK UP",
            font_size=dp(11),
            bold=True,
            color=(0.65, 0.65, 0.65, 1),
            halign="center",
            valign="middle",
            size_hint=(1, 0.35),
        )
        header.bind(size=header.setter("text_size"))

        self.projects_lbl = Label(
            text="–",
            font_size=dp(14),
            bold=True,
            color=TEXT_LIGHT,
            halign="center",
            valign="middle",
            size_hint=(1, 0.65),
        )
        self.projects_lbl.bind(size=self.projects_lbl.setter("text_size"))

        layout.add_widget(header)
        layout.add_widget(self.projects_lbl)
        self.add_widget(layout)

    def set_value(self, val):
        self.projects_lbl.text = str(val) if val else "None"


# ─────────────────────────────────────────────
#  STATUS BAR
# ─────────────────────────────────────────────
class StatusBar(BoxLayout):
    """Bottom bar: last sync time + manual refresh button."""

    def __init__(self, refresh_callback, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint=(1, None),
            height=dp(34),
            padding=[dp(12), 0],
            spacing=dp(10),
            **kwargs,
        )
        with self.canvas.before:
            Color(0.10, 0.10, 0.10, 1)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(
            pos=lambda i, v: setattr(self._bg, "pos", i.pos),
            size=lambda i, v: setattr(self._bg, "size", i.size),
        )

        self.sync_lbl = Label(
            text="Not yet synced",
            font_size=dp(11),
            color=(0.50, 0.50, 0.50, 1),
            halign="left",
            valign="middle",
            size_hint=(1, 1),
        )
        self.sync_lbl.bind(size=self.sync_lbl.setter("text_size"))

        refresh_btn = Button(
            text="⟳  Refresh",
            font_size=dp(12),
            bold=True,
            color=TEXT_LIGHT,
            background_color=(0, 0, 0, 0),
            background_normal="",
            size_hint=(None, 1),
            width=dp(90),
        )
        with refresh_btn.canvas.before:
            Color(0.25, 0.25, 0.25, 1)
            rr = RoundedRectangle(pos=refresh_btn.pos, size=refresh_btn.size, radius=[dp(6)])
        refresh_btn.bind(
            pos=lambda i, v: setattr(rr, "pos", i.pos),
            size=lambda i, v: setattr(rr, "size", i.size),
        )
        refresh_btn.bind(on_press=lambda *a: refresh_callback())

        self.add_widget(self.sync_lbl)
        self.add_widget(refresh_btn)

    def set_sync_time(self, time_str):
        self.sync_lbl.text = f"Last synced: {time_str}"


# ─────────────────────────────────────────────
#  ROOT LAYOUT
# ─────────────────────────────────────────────
class MakerspaceRoot(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(6), **kwargs)

        with self.canvas.before:
            Color(*BG_COLOR)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(
            pos=lambda i, v: setattr(self._bg, "pos", i.pos),
            size=lambda i, v: setattr(self._bg, "size", i.size),
        )

        # Connect to Google Sheets
        self.sheets = None
        self._connect_sheets()

        # ── Header ──────────────────────────────────────────────────────
        self.add_widget(Label(
            text="MAKERSPACE CONTROL",
            font_size=dp(15),
            bold=True,
            color=(0.80, 0.80, 0.80, 1),
            size_hint=(1, None),
            height=dp(36),
        ))

        # ── Row 1: four counter tiles ────────────────────────────────────
        row1 = BoxLayout(
            orientation="horizontal",
            spacing=dp(10),
            padding=[dp(12), 0, dp(12), 0],
            size_hint=(1, 1),
        )
        self.drills_tile   = CounterTile("Available\nDrills",      "drills",       YELLOW_TILE, BTN_YELLOW, self.sheets)
        self.calipers_tile = CounterTile("Available\nCalipers",    "calipers",     YELLOW_TILE, BTN_YELLOW, self.sheets)
        self.glue_tile     = CounterTile("Available\nGlue",        "glue",         YELLOW_TILE, BTN_YELLOW, self.sheets)
        self.printer_tile  = CounterTile("Available\n3D Printers", "printer_open", BLUE_TILE,   BTN_BLUE,   self.sheets)

        for tile in [self.drills_tile, self.calipers_tile, self.glue_tile, self.printer_tile]:
            row1.add_widget(tile)
        self.add_widget(row1)

        # ── Row 2: queue | machine shop | hours (double-wide) ────────────
        #
        # Kivy GridLayout has no colspan, so row 2 is a BoxLayout.
        # The hours tile gets size_hint_x=2 so it occupies twice the width
        # of each single tile — exactly matching your mockup.
        #
        row2 = BoxLayout(
            orientation="horizontal",
            spacing=dp(10),
            padding=[dp(12), 0, dp(12), dp(8)],
            size_hint=(1, 1),
        )
        self.queue_tile   = CounterTile("3D Prints\nin Queue", "printer_queue", BLUE_TILE, BTN_BLUE, self.sheets)
        self.machine_tile = MachineShopTile(self.sheets)
        self.hours_tile   = HoursTile()

        self.queue_tile.size_hint_x   = 1
        self.machine_tile.size_hint_x = 1
        self.hours_tile.size_hint_x   = 2   # spans two tile-widths

        row2.add_widget(self.queue_tile)
        row2.add_widget(self.machine_tile)
        row2.add_widget(self.hours_tile)
        self.add_widget(row2)

        # ── Projects bar ─────────────────────────────────────────────────
        self.projects_tile = ProjectsTile(size_hint=(1, None), height=dp(56))
        self.add_widget(self.projects_tile)

        # ── Status bar ───────────────────────────────────────────────────
        self.status_bar = StatusBar(refresh_callback=self.refresh)
        self.add_widget(self.status_bar)

        # ── Auto-poll ────────────────────────────────────────────────────
        Clock.schedule_once(lambda dt: self.refresh(), 1)
        Clock.schedule_interval(lambda dt: self.refresh(), POLL_INTERVAL)

    # ── Sheets ───────────────────────────────────────────────────────────
    def _connect_sheets(self):
        try:
            self.sheets = SheetsClient()
        except Exception as e:
            print(f"[Sheets] Connection failed: {e}")
            self.sheets = None

    def refresh(self):
        if self.sheets is None:
            self._connect_sheets()
            if self.sheets is None:
                self.status_bar.set_sync_time("Connection failed – retrying…")
                return
        threading.Thread(target=self._fetch, daemon=True).start()

    def _fetch(self):
        try:
            data = self.sheets.read_all()
            Clock.schedule_once(lambda dt: self._apply(data), 0)
        except Exception as e:
            print(f"[Sheets] Refresh error: {e}")
            Clock.schedule_once(
                lambda dt: self.status_bar.set_sync_time("Refresh failed"), 0
            )

    def _apply(self, data):
        from datetime import datetime
        self.drills_tile.set_value(data.get("drills", 0))
        self.calipers_tile.set_value(data.get("calipers", 0))
        self.glue_tile.set_value(data.get("glue", 0))
        self.printer_tile.set_value(data.get("printer_open", 0))
        self.queue_tile.set_value(data.get("printer_queue", 0))
        self.machine_tile.set_value(data.get("machine_shop", "CLOSED"))

        # Both hour chips updated from their respective sheet cells
        self.hours_tile.set_value(
            data.get("hours_session1", "–"),
            data.get("hours_session2", "–"),
        )

        self.projects_tile.set_value(data.get("projects", "None"))
        self.status_bar.set_sync_time(datetime.now().strftime("%I:%M:%S %p"))


# ─────────────────────────────────────────────
#  APP ENTRY POINT
# ─────────────────────────────────────────────
class MakerspaceApp(App):
    def build(self):
        Window.size = (800, 480)   # standard 5" Pi touchscreen resolution
        Window.clearcolor = BG_COLOR
        return MakerspaceRoot()


if __name__ == "__main__":
    MakerspaceApp().run()
