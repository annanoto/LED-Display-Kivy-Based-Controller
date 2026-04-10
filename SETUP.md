# Makerspace Controller – Raspberry Pi Setup Guide

## Hardware
- Raspberry Pi 3B
- 5" HDMI touchscreen (800×480)

---

## 1. Install Dependencies

```bash
sudo apt update && sudo apt upgrade -y

# Kivy dependencies
sudo apt install -y python3-pip libsdl2-dev libsdl2-image-dev \
  libsdl2-mixer-dev libsdl2-ttf-dev libportmidi-dev \
  libswscale-dev libavformat-dev libavcodec-dev zlib1g-dev

# Python packages
pip3 install kivy gspread google-auth
```

---

## 2. Google Service Account

1. Go to [Google Cloud Console](https://console.cloud.google.com)
2. Create a project → Enable **Google Sheets API**
3. Create a **Service Account** → download the JSON key
4. Rename the JSON file to `service_account.json`
5. Place it in the same folder as `makerspace_controller.py`
6. **Share your Google Sheet** with the service account email
   (looks like `something@project.iam.gserviceaccount.com`) — give it **Editor** access

---

## 3. Configure the Script

Open `makerspace_controller.py` and update:

```python
SERVICE_ACCOUNT_FILE = "service_account.json"   # path to your JSON key
SHEET_ID = "YOUR_GOOGLE_SHEET_ID_HERE"          # from your sheet's URL
```

The Sheet ID is the long string in your sheet URL:
`https://docs.google.com/spreadsheets/d/  >>>THIS_PART<<<  /edit`

### Cell Map
The `CELL_MAP` dict maps data fields to cell addresses. 
**Verify these match your sheet exactly:**

```python
CELL_MAP = {
    "drills":        "B3",
    "calipers":      "B4",
    "glue":          "B5",
    "printer_open":  "E3",
    "printer_queue": "E4",
    "machine_shop":  "B7",    # Should contain "OPEN" or "CLOSED"
    "machine_reopen":"B8",
    "hours":         "D8",
    "projects":      "B11",
}
```

---

## 4. Run the App

```bash
cd /path/to/your/folder
python3 makerspace_controller.py
```

### Auto-start on boot (optional)

Create `/etc/systemd/system/makerspace.service`:

```ini
[Unit]
Description=Makerspace Controller
After=graphical.target

[Service]
User=pi
WorkingDirectory=/home/pi/makerspace
ExecStart=/usr/bin/python3 /home/pi/makerspace/makerspace_controller.py
Environment=DISPLAY=:0
Restart=on-failure

[Install]
WantedBy=graphical.target
```

Then enable it:
```bash
sudo systemctl enable makerspace.service
sudo systemctl start makerspace.service
```

---

## 5. Touchscreen Calibration

If touch input is offset, install `xinput-calibrator`:
```bash
sudo apt install xinput-calibrator
xinput_calibrator
```
Follow the on-screen prompts and save the output to `/etc/X11/xorg.conf.d/99-calibration.conf`.

---

## How It Works

```
Button pressed on Pi touchscreen
        ↓
Kivy updates count / toggles status locally (instant UI feedback)
        ↓
Background thread calls gspread → writes new value to Google Sheet cell
        ↓
Your existing LED matrix script detects sheet change → updates display
```

The controller also **polls the sheet every 15 seconds** (configurable via `POLL_INTERVAL`)
so any changes made directly in the sheet are reflected on the Pi controller too.
