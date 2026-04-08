# Fingerprint Attendance Setup

## Hardware
- ESP32-DevKit v1
- R305 or GT-521F52 fingerprint sensor (UART)
- SSD1306 128x64 OLED (I2C)
- Buzzer + 220Ω resistor (optional)
- Momentary button for enrollment (GPIO0 with INPUT_PULLUP)

### Wiring (ESP32)
- Sensor VCC -> 5V, GND -> GND, TX -> GPIO16 (RX2), RX -> GPIO17 (TX2)
- OLED VCC -> 3V3, GND -> GND, SCL -> GPIO22, SDA -> GPIO21
- Enroll button -> GPIO0 to GND
- Buzzer -> GPIO27 -> 220Ω -> GND

Keep all grounds common. Use short twisted wires for UART to reduce noise.

## Firmware
The reference client lives at `firmware/esp32_fingerprint.ino`.
1. Install Arduino core for ESP32.
2. Libraries: Adafruit Fingerprint Sensor Library, Adafruit SSD1306, ArduinoJson, HTTPClient (built-in with ESP32 core).
3. Edit SSID/PASS and backend URL at the top of the sketch.
4. Flash to ESP32. The enroll button triggers a two-scan capture; templates are stored on the sensor and optionally uploaded to the backend.

## Backend (this repo)
The Flask app now exposes fingerprint endpoints:
- `GET /api/finger/next-id` → `{ next_id }`
- `POST /api/finger/enroll` with `{ name, finger_id?, template_hex? }` → upserts person + fingerprint mapping.
- `POST /api/finger/check` with `{ finger_id, action?, location?, lat?, lon?, device_id? }` → marks attendance, applies duplicate window (`DUP_WINDOW_MIN`, default 3 minutes).

Database changes (SQLite):
- `people` now allows `encoding` to be NULL and includes `finger_id`, `finger_template` columns.
- Attendance stays in the shared `attendance` table, so the dashboard shows face and fingerprint punches together.

## Duplicate protection
Both face and fingerprint check-ins are blocked if the last record for that person is newer than `DUP_WINDOW_MIN` minutes. Adjust via env var before starting the Flask app:
```
export DUP_WINDOW_MIN=5
python attendance_app.py
```

## Quick test (without hardware)
- Insert a dummy person with `finger_id`:
```
sqlite3 attendance.db "INSERT INTO people(name, finger_id, created_at) VALUES ('Test User', 1, datetime('now'));"
```
- Simulate a punch:
```
curl -X POST http://localhost:5000/api/finger/check \
  -H 'Content-Type: application/json' \
  -d '{"finger_id":1,"device_id":"sim","location":"Lab"}'
```

## Notes
- If you prefer MySQL, mirror the schema in `attendance_app.py` (people + attendance) and point SQLAlchemy/connector there; the HTTP contract remains unchanged.
- GT-521F52 uses 3.3–5V and may ship with a different baud; set `fingerSerial.begin(57600...)` accordingly.
- For kiosk UX, mount the OLED near the scanner and keep the enroll button accessible to admins only.
