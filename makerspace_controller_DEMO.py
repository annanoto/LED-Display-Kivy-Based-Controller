"""
Makerspace Controller - DEMO MODE
===================================
No Google Sheets connection required.
All data is stored in memory using FAKE_DATA below.

Run with:
  pip install kivy
  python3 makerspace_controller_DEMO.py

The layout, colors, and interactions are identical to the real controller.
Every action that would write to Google Sheets is instead logged in the
"Simulated Sheet Writes" panel at the bottom so you can verify behavior.
"""

from kivy.app import App
from kivy.uix.boxlayout import BoxLayout
from kivy.uix.floatlayout import FloatLayout
from kivy.uix.label import Label
from kivy.uix.button import Button
from kivy.uix.scrollview import ScrollView
from kivy.graphics import Color, RoundedRectangle, Rectangle
from kivy.clock import Clock
from kivy.core.window import Window
from kivy.metrics import dp
from datetime import datetime

# ─────────────────────────────────────────────
#  FAKE DATA  (stands in for Google Sheet)
# ─────────────────────────────────────────────
FAKE_DATA = {
    "drills":          2,
    "calipers":        4,
    "glue":            6,
    "printer_open":    0,
    "printer_queue":   2,
    "machine_shop":    "CLOSED",
    "machine_reopen":  "3PM TODAY",
    "hours_session1":  "9:00-5:00",
    "hours_session2":  "9:00-8:00",
    "projects":        "Noto Bracket, Tandy Housing, & 4 Others",
}

# Log of every simulated sheet write
WRITE_LOG = []

# ─────────────────────────────────────────────
#  COLORS
# ─────────────────────────────────────────────
BG_COLOR    = (0.05, 0.05, 0.05, 1)
YELLOW_TILE = (0.99, 0.78, 0.28, 1)
BLUE_TILE   = (0.40, 0.75, 0.90, 1)
RED_TILE    = (0.92, 0.26, 0.26, 1)
GREEN_TILE  = (0.18, 0.85, 0.40, 1)
BROWN_TILE  = (0.60, 0.35, 0.05, 1)
CHIP_YELLOW = (0.99, 0.78, 0.10, 1)
CHIP_DARK   = (0.42, 0.24, 0.03, 1)
BTN_YELLOW  = (0.55, 0.48, 0.30, 1)
BTN_BLUE    = (0.30, 0.55, 0.70, 1)
TEXT_DARK   = (0.10, 0.10, 0.10, 1)
TEXT_LIGHT  = (0.95, 0.95, 0.95, 1)
LOG_BG      = (0.08, 0.08, 0.08, 1)
LOG_TEXT    = (0.40, 0.90, 0.55, 1)   # green terminal color


# ─────────────────────────────────────────────
#  SIMULATED SHEETS CLIENT
# ─────────────────────────────────────────────
class FakeSheetsClient:
    """
    Drop-in replacement for SheetsClient.
    Reads/writes to FAKE_DATA in memory and logs all writes.
    """

    def read_all(self):
        return dict(FAKE_DATA)

    def write_cell(self, cell_key, value):
        FAKE_DATA[cell_key] = value
        timestamp = datetime.now().strftime("%H:%M:%S")
        entry = f"[{timestamp}]  {cell_key:20s} ← {value}"
        WRITE_LOG.append(entry)
        # Keep log from growing unbounded
        if len(WRITE_LOG) > 50:
            WRITE_LOG.pop(0)
        # Notify the log widget to refresh (scheduled on main thread)
        Clock.schedule_once(lambda dt: _refresh_log_widget(), 0)


# Global reference so FakeSheetsClient can trigger a UI update
_log_widget_ref = None

def _refresh_log_widget():
    if _log_widget_ref is not None:
        _log_widget_ref.refresh()


# ─────────────────────────────────────────────
#  BASE TILE
# ─────────────────────────────────────────────
class RoundedTile(FloatLayout):
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
#  COUNTER TILE
# ─────────────────────────────────────────────
class CounterTile(RoundedTile):
    def __init__(self, title, cell_key, bg_color, btn_color, sheets_ref, **kwargs):
        super().__init__(bg_color=bg_color, **kwargs)
        self.cell_key = cell_key
        self.sheets_ref = sheets_ref
        self.count = 0

        layout = BoxLayout(
            orientation="vertical",
            padding=dp(8), spacing=dp(4),
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        )

        self.title_lbl = Label(
            text=title, font_size=dp(13), bold=True, color=TEXT_DARK,
            halign="center", valign="middle", size_hint=(1, 0.22),
        )
        self.title_lbl.bind(size=self.title_lbl.setter("text_size"))

        self.count_lbl = Label(
            text="–", font_size=dp(52), bold=True, color=TEXT_DARK,
            halign="center", valign="middle", size_hint=(1, 0.50),
        )
        self.count_lbl.bind(size=self.count_lbl.setter("text_size"))

        btn_row = BoxLayout(
            orientation="horizontal", spacing=dp(8),
            size_hint=(1, 0.28), padding=[dp(10), 0, dp(10), 0],
        )
        btn_row.add_widget(self._make_btn("−", btn_color, self._decrement))
        btn_row.add_widget(self._make_btn("+", btn_color, self._increment))

        layout.add_widget(self.title_lbl)
        layout.add_widget(self.count_lbl)
        layout.add_widget(btn_row)
        self.add_widget(layout)

    def _make_btn(self, text, color, callback):
        btn = Button(
            text=text, font_size=dp(20), bold=True, color=TEXT_DARK,
            background_color=(0, 0, 0, 0), background_normal="",
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
        self.sheets_ref.write_cell(self.cell_key, self.count)

    def _decrement(self, *args):
        if self.count > 0:
            self.count -= 1
            self.count_lbl.text = str(self.count)
            self.sheets_ref.write_cell(self.cell_key, self.count)


# ─────────────────────────────────────────────
#  MACHINE SHOP TILE
# ─────────────────────────────────────────────
class MachineShopTile(RoundedTile):
    def __init__(self, sheets_ref, **kwargs):
        super().__init__(bg_color=RED_TILE, **kwargs)
        self.sheets_ref = sheets_ref
        self.is_open = False

        layout = BoxLayout(
            orientation="vertical", padding=dp(10),
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        )

        self.header_lbl = Label(
            text="Machine\nShop", font_size=dp(13), bold=True, color=TEXT_DARK,
            halign="center", valign="middle", size_hint=(1, 0.35),
        )
        self.header_lbl.bind(size=self.header_lbl.setter("text_size"))

        self.status_lbl = Label(
            text="CLOSED", font_size=dp(28), bold=True, color=TEXT_DARK,
            halign="center", valign="middle", size_hint=(1, 0.65),
        )
        self.status_lbl.bind(size=self.status_lbl.setter("text_size"))

        layout.add_widget(self.header_lbl)
        layout.add_widget(self.status_lbl)
        self.add_widget(layout)

        touch_btn = Button(
            background_color=(0, 0, 0, 0), background_normal="",
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        )
        touch_btn.bind(on_press=self._toggle)
        self.add_widget(touch_btn)

    def set_value(self, val):
        self.is_open = str(val).strip().upper() == "OPEN"
        self._apply()

    def _toggle(self, *args):
        self.is_open = not self.is_open
        self._apply()
        self.sheets_ref.write_cell("machine_shop", "OPEN" if self.is_open else "CLOSED")

    def _apply(self):
        self.set_color(GREEN_TILE if self.is_open else RED_TILE)
        self.status_lbl.text = "OPEN" if self.is_open else "CLOSED"


# ─────────────────────────────────────────────
#  HOURS CHIP + TILE
# ─────────────────────────────────────────────
class HoursChip(FloatLayout):
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
            text="–", font_size=dp(15), bold=True, color=TEXT_DARK,
            halign="center", valign="middle",
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        )
        self.label.bind(size=self.label.setter("text_size"))
        self.add_widget(self.label)

    def set_text(self, text):
        self.label.text = str(text) if text else "–"


class HoursTile(RoundedTile):
    def __init__(self, **kwargs):
        super().__init__(bg_color=BROWN_TILE, **kwargs)

        layout = BoxLayout(
            orientation="vertical",
            padding=[dp(10), dp(8), dp(10), dp(8)], spacing=dp(6),
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        )

        header = Label(
            text="Today's Hours", font_size=dp(13), bold=True, color=TEXT_LIGHT,
            halign="center", valign="middle", size_hint=(1, 0.28),
        )
        header.bind(size=header.setter("text_size"))

        chips_row = BoxLayout(orientation="horizontal", spacing=dp(10), size_hint=(1, 0.72))
        self.chip1 = HoursChip(chip_color=CHIP_YELLOW, size_hint=(1, 1))
        self.chip2 = HoursChip(chip_color=CHIP_DARK,   size_hint=(1, 1))
        chips_row.add_widget(self.chip1)
        chips_row.add_widget(self.chip2)

        layout.add_widget(header)
        layout.add_widget(chips_row)
        self.add_widget(layout)

    def set_value(self, session1, session2):
        self.chip1.set_text(session1)
        self.chip2.set_text(session2)


# ─────────────────────────────────────────────
#  PROJECTS BAR
# ─────────────────────────────────────────────
class ProjectsTile(RoundedTile):
    def __init__(self, **kwargs):
        super().__init__(bg_color=(0.15, 0.15, 0.15, 1), radius=12, **kwargs)

        layout = BoxLayout(
            orientation="vertical", padding=dp(8), spacing=dp(2),
            size_hint=(1, 1), pos_hint={"x": 0, "y": 0},
        )

        header = Label(
            text="PROJECTS READY FOR PICK UP", font_size=dp(11), bold=True,
            color=(0.65, 0.65, 0.65, 1), halign="center", valign="middle",
            size_hint=(1, 0.35),
        )
        header.bind(size=header.setter("text_size"))

        self.projects_lbl = Label(
            text="–", font_size=dp(14), bold=True, color=TEXT_LIGHT,
            halign="center", valign="middle", size_hint=(1, 0.65),
        )
        self.projects_lbl.bind(size=self.projects_lbl.setter("text_size"))

        layout.add_widget(header)
        layout.add_widget(self.projects_lbl)
        self.add_widget(layout)

    def set_value(self, val):
        self.projects_lbl.text = str(val) if val else "None"


# ─────────────────────────────────────────────
#  SHEET WRITE LOG WIDGET  (demo-only)
# ─────────────────────────────────────────────
class WriteLogWidget(BoxLayout):
    """
    Shows every simulated sheet write in a scrollable terminal-style panel.
    This widget only exists in demo mode — the real controller has a status bar here.
    """

    def __init__(self, **kwargs):
        super().__init__(
            orientation="vertical",
            size_hint=(1, None),
            height=dp(90),
            **kwargs,
        )
        global _log_widget_ref
        _log_widget_ref = self

        with self.canvas.before:
            Color(*LOG_BG)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(
            pos=lambda i, v: setattr(self._bg, "pos", i.pos),
            size=lambda i, v: setattr(self._bg, "size", i.size),
        )

        header_row = BoxLayout(
            orientation="horizontal",
            size_hint=(1, None), height=dp(20),
            padding=[dp(10), 0],
        )
        header_row.add_widget(Label(
            text="◉  DEMO MODE — Simulated Sheet Writes",
            font_size=dp(10), bold=True,
            color=(0.40, 0.90, 0.55, 1),
            halign="left", valign="middle",
        ))
        self.add_widget(header_row)

        self.scroll = ScrollView(size_hint=(1, 1))
        self.log_lbl = Label(
            text="No writes yet. Press a button to see simulated sheet updates.",
            font_size=dp(10),
            color=LOG_TEXT,
            halign="left",
            valign="top",
            size_hint=(1, None),
            markup=True,
        )
        self.log_lbl.bind(texture_size=self.log_lbl.setter("size"))
        self.scroll.add_widget(self.log_lbl)
        self.add_widget(self.scroll)

    def refresh(self):
        if WRITE_LOG:
            # Show most recent entries at top
            self.log_lbl.text = "\n".join(reversed(WRITE_LOG[-12:]))
            # Scroll to top to show newest entry
            self.scroll.scroll_y = 1
        else:
            self.log_lbl.text = "No writes yet."


# ─────────────────────────────────────────────
#  STATUS BAR  (demo variant)
# ─────────────────────────────────────────────
class StatusBar(BoxLayout):
    def __init__(self, refresh_callback, **kwargs):
        super().__init__(
            orientation="horizontal",
            size_hint=(1, None), height=dp(30),
            padding=[dp(12), 0], spacing=dp(10),
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
            text="DEMO MODE  —  data is local only",
            font_size=dp(10), color=(0.40, 0.90, 0.55, 1),
            halign="left", valign="middle", size_hint=(1, 1),
        )
        self.sync_lbl.bind(size=self.sync_lbl.setter("text_size"))

        refresh_btn = Button(
            text="⟳  Reset Demo Data",
            font_size=dp(11), bold=True, color=TEXT_LIGHT,
            background_color=(0, 0, 0, 0), background_normal="",
            size_hint=(None, 1), width=dp(130),
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


# ─────────────────────────────────────────────
#  ROOT LAYOUT
# ─────────────────────────────────────────────
class MakerspaceRoot(BoxLayout):

    def __init__(self, **kwargs):
        super().__init__(orientation="vertical", spacing=dp(4), **kwargs)

        with self.canvas.before:
            Color(*BG_COLOR)
            self._bg = Rectangle(pos=self.pos, size=self.size)
        self.bind(
            pos=lambda i, v: setattr(self._bg, "pos", i.pos),
            size=lambda i, v: setattr(self._bg, "size", i.size),
        )

        self.sheets = FakeSheetsClient()

        # ── Header ──────────────────────────────────────────────────────
        header_row = BoxLayout(
            orientation="horizontal",
            size_hint=(1, None), height=dp(32),
            padding=[dp(12), 0],
        )
        header_row.add_widget(Label(
            text="MAKERSPACE CONTROL",
            font_size=dp(15), bold=True, color=(0.80, 0.80, 0.80, 1),
            halign="left", valign="middle", size_hint=(1, 1),
        ))
        header_row.add_widget(Label(
            text="[ DEMO MODE ]",
            font_size=dp(11), bold=True, color=(0.40, 0.90, 0.55, 1),
            halign="right", valign="middle", size_hint=(None, 1), width=dp(110),
        ))
        self.add_widget(header_row)

        # ── Row 1: four counter tiles ────────────────────────────────────
        row1 = BoxLayout(
            orientation="horizontal", spacing=dp(10),
            padding=[dp(12), 0, dp(12), 0], size_hint=(1, 1),
        )
        self.drills_tile   = CounterTile("Available\nDrills",      "drills",       YELLOW_TILE, BTN_YELLOW, self.sheets)
        self.calipers_tile = CounterTile("Available\nCalipers",    "calipers",     YELLOW_TILE, BTN_YELLOW, self.sheets)
        self.glue_tile     = CounterTile("Available\nGlue",        "glue",         YELLOW_TILE, BTN_YELLOW, self.sheets)
        self.printer_tile  = CounterTile("Available\n3D Printers", "printer_open", BLUE_TILE,   BTN_BLUE,   self.sheets)
        for tile in [self.drills_tile, self.calipers_tile, self.glue_tile, self.printer_tile]:
            row1.add_widget(tile)
        self.add_widget(row1)

        # ── Row 2: queue | machine shop | hours (double-wide) ────────────
        row2 = BoxLayout(
            orientation="horizontal", spacing=dp(10),
            padding=[dp(12), 0, dp(12), 0], size_hint=(1, 1),
        )
        self.queue_tile   = CounterTile("3D Prints\nin Queue", "printer_queue", BLUE_TILE, BTN_BLUE, self.sheets)
        self.machine_tile = MachineShopTile(self.sheets)
        self.hours_tile   = HoursTile()

        self.queue_tile.size_hint_x   = 1
        self.machine_tile.size_hint_x = 1
        self.hours_tile.size_hint_x   = 2

        row2.add_widget(self.queue_tile)
        row2.add_widget(self.machine_tile)
        row2.add_widget(self.hours_tile)
        self.add_widget(row2)

        # ── Projects bar ─────────────────────────────────────────────────
        self.projects_tile = ProjectsTile(size_hint=(1, None), height=dp(50))
        self.add_widget(self.projects_tile)

        # ── Status bar ───────────────────────────────────────────────────
        self.status_bar = StatusBar(refresh_callback=self._reset_demo)
        self.add_widget(self.status_bar)

        # ── Write log (demo only) ─────────────────────────────────────────
        self.write_log = WriteLogWidget()
        self.add_widget(self.write_log)

        # Load initial fake data
        Clock.schedule_once(lambda dt: self._load_fake_data(), 0.2)

    def _load_fake_data(self):
        """Apply the FAKE_DATA dict to all tiles."""
        data = self.sheets.read_all()
        self.drills_tile.set_value(data["drills"])
        self.calipers_tile.set_value(data["calipers"])
        self.glue_tile.set_value(data["glue"])
        self.printer_tile.set_value(data["printer_open"])
        self.queue_tile.set_value(data["printer_queue"])
        self.machine_tile.set_value(data["machine_shop"])
        self.hours_tile.set_value(data["hours_session1"], data["hours_session2"])
        self.projects_tile.set_value(data["projects"])

    def _reset_demo(self):
        """Reset all values back to the original FAKE_DATA defaults."""
        FAKE_DATA.update({
            "drills":          2,
            "calipers":        4,
            "glue":            6,
            "printer_open":    0,
            "printer_queue":   2,
            "machine_shop":    "CLOSED",
            "machine_reopen":  "3PM TODAY",
            "hours_session1":  "9:00-5:00",
            "hours_session2":  "9:00-8:00",
            "projects":        "Noto Bracket, Tandy Housing, & 4 Others",
        })
        WRITE_LOG.clear()
        self._load_fake_data()
        self.write_log.refresh()


# ─────────────────────────────────────────────
#  APP ENTRY POINT
# ─────────────────────────────────────────────
class MakerspaceApp(App):
    def build(self):
        Window.size = (800, 480)
        Window.clearcolor = BG_COLOR
        return MakerspaceRoot()


if __name__ == "__main__":
    MakerspaceApp().run()
