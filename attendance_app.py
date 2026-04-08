import base64
import io
import os
import socket
import sys
import sqlite3
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import List, Tuple

import cv2
import csv
import face_recognition
import numpy as np
from flask import Flask, jsonify, render_template, request, send_file

from location_utils import resolve_location

APP_ROOT = Path(__file__).parent
DB_PATH = APP_ROOT / "attendance.db"
MATCH_THRESHOLD = 0.48
DUP_WINDOW_MIN = int(os.environ.get("DUP_WINDOW_MIN", "3"))


def ensure_db() -> None:
    """Create tables and run lightweight migrations."""
    conn = sqlite3.connect(DB_PATH)

    # Base tables (new installs)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS people (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE NOT NULL,
            encoding BLOB,
            finger_id INTEGER UNIQUE,
            finger_template BLOB,
            created_at TEXT NOT NULL
        )
        """
    )
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS attendance (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            person_id INTEGER NOT NULL,
            ts TEXT NOT NULL,
            day TEXT NOT NULL,
            location TEXT,
            lat REAL,
            lon REAL,
            check_out_ts TEXT,
            FOREIGN KEY(person_id) REFERENCES people(id),
            UNIQUE(person_id, day)
        )
        """
    )

    # --- Migrations for existing deployments ---
    info = conn.execute("PRAGMA table_info(people)").fetchall()
    cols = {col[1]: col for col in info}

    # Rebuild people table if encoding is NOT NULL (older schema) or missing fingerprint columns
    needs_rebuild = False
    if cols:
        encoding_notnull = cols.get("encoding", (None, None, None, 0))[3] == 1
        missing_finger_id = "finger_id" not in cols
        missing_finger_template = "finger_template" not in cols
        needs_rebuild = encoding_notnull or missing_finger_id or missing_finger_template

    if needs_rebuild:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS people_new (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT UNIQUE NOT NULL,
                encoding BLOB,
                finger_id INTEGER UNIQUE,
                finger_template BLOB,
                created_at TEXT NOT NULL
            )
            """
        )
        # Copy existing data; finger columns default to NULL
        existing_cols = "id, name, encoding, created_at"
        conn.execute(
            f"INSERT INTO people_new ({existing_cols}) SELECT {existing_cols} FROM people"
        )
        conn.execute("DROP TABLE people")
        conn.execute("ALTER TABLE people_new RENAME TO people")
        conn.execute("PRAGMA foreign_keys=ON")

    # Add attendance columns if missing
    try:
        conn.execute("ALTER TABLE attendance ADD COLUMN location TEXT DEFAULT 'Unknown Location'")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE attendance ADD COLUMN check_out_ts TEXT")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE attendance ADD COLUMN lat REAL")
    except sqlite3.OperationalError:
        pass

    try:
        conn.execute("ALTER TABLE attendance ADD COLUMN lon REAL")
    except sqlite3.OperationalError:
        pass

    conn.commit()
    conn.close()


def np_to_blob(arr: np.ndarray) -> bytes:
    buffer = io.BytesIO()
    np.save(buffer, arr)
    return buffer.getvalue()


def blob_to_np(blob: bytes) -> np.ndarray:
    return np.load(io.BytesIO(blob), allow_pickle=False)


def decode_image(data_url: str) -> np.ndarray:
    """Decode a base64 data URL into a BGR image for OpenCV."""
    if "," in data_url:
        data_url = data_url.split(",", 1)[1]
    raw = base64.b64decode(data_url)
    arr = np.frombuffer(raw, dtype=np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    return img


def fetch_known_encodings() -> List[Tuple[int, str, np.ndarray]]:
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute("SELECT id, name, encoding FROM people WHERE encoding IS NOT NULL").fetchall()
    conn.close()
    return [(row[0], row[1], blob_to_np(row[2])) for row in rows]


app = Flask(__name__, template_folder=str(APP_ROOT / "templates"), static_folder=str(APP_ROOT / "static"))

# Cached in-memory encodings; refreshed on enroll
known_faces: List[Tuple[int, str, np.ndarray]] = []


def next_finger_id(conn: sqlite3.Connection) -> int:
    row = conn.execute("SELECT COALESCE(MAX(finger_id), 0) + 1 FROM people").fetchone()
    return int(row[0] or 1)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/dashboard")
def dashboard():
    conn = sqlite3.connect(DB_PATH)
    total_people = conn.execute("SELECT COUNT(*) FROM people").fetchone()[0]
    today = date.today().isoformat()
    today_attendance = conn.execute("SELECT COUNT(*) FROM attendance WHERE day = ?", (today,)).fetchone()[0]
    
    recent_records = conn.execute(
        """
        SELECT p.name, a.ts, a.day, a.location, a.check_out_ts, a.lat, a.lon
        FROM attendance a
        JOIN people p ON a.person_id = p.id
        ORDER BY a.ts DESC
        LIMIT 50
        """
    ).fetchall()
    conn.close()
    
    return render_template(
        "dashboard.html", 
        total_people=total_people,
        today_attendance=today_attendance,
        recent_records=recent_records
    )


@app.route("/api/finger/next-id", methods=["GET"])
def api_next_finger_id():
    conn = sqlite3.connect(DB_PATH)
    nf = next_finger_id(conn)
    conn.close()
    return jsonify({"next_id": nf})


@app.route("/api/finger/enroll", methods=["POST"])
def enroll_fingerprint():
    payload = request.get_json(force=True)
    if not payload or "name" not in payload:
        return jsonify({"error": "name is required"}), 400

    name = payload["name"].strip()
    finger_id = payload.get("finger_id")
    template_hex = payload.get("template_hex")

    if not name:
        return jsonify({"error": "name cannot be empty"}), 400

    conn = sqlite3.connect(DB_PATH)
    if finger_id is None:
        finger_id = next_finger_id(conn)
    try:
        finger_id = int(finger_id)
    except (TypeError, ValueError):
        conn.close()
        return jsonify({"error": "finger_id must be an integer"}), 400

    finger_template = None
    if template_hex:
        try:
            finger_template = bytes.fromhex(template_hex)
        except ValueError:
            conn.close()
            return jsonify({"error": "template_hex must be hex-encoded"}), 400

    try:
        conn.execute(
            """
            INSERT INTO people(name, encoding, finger_id, finger_template, created_at)
            VALUES (?, NULL, ?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
                finger_id=excluded.finger_id,
                finger_template=COALESCE(excluded.finger_template, people.finger_template)
            """,
            (name, finger_id, finger_template, datetime.utcnow().isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "finger_id already in use"}), 409
    conn.close()

    # Refresh face cache (in case the same person had a face encoding)
    global known_faces
    known_faces = fetch_known_encodings()

    return jsonify({"status": "enrolled", "name": name, "finger_id": finger_id})


@app.route("/api/enroll", methods=["POST"])
def enroll():
    payload = request.get_json()
    if not payload or "name" not in payload or "image" not in payload:
        return jsonify({"error": "name and image fields are required"}), 400

    name = payload["name"].strip()
    if not name:
        return jsonify({"error": "name cannot be empty"}), 400

    image_bgr = decode_image(payload["image"])
    if image_bgr is None:
        return jsonify({"error": "could not decode image"}), 400

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    encodings = face_recognition.face_encodings(rgb)
    if not encodings:
        return jsonify({"error": "No face detected. Please try again."}), 400
    
    if len(encodings) > 1:
        return jsonify({"error": "Multiple people detected. Only one person can enroll at a time."}), 400

    encoding = encodings[0]

    conn = sqlite3.connect(DB_PATH)
    try:
        conn.execute(
            "INSERT INTO people(name, encoding, created_at) VALUES (?, ?, ?)",
            (name, np_to_blob(encoding), datetime.utcnow().isoformat()),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({"error": "name already exists"}), 409
    conn.close()

    # refresh cache
    global known_faces
    known_faces = fetch_known_encodings()

    return jsonify({"status": "enrolled", "name": name})


@app.route("/api/finger/check", methods=["POST"])
def finger_check():
    payload = request.get_json(force=True)
    if not payload or "finger_id" not in payload:
        return jsonify({"error": "finger_id is required"}), 400

    try:
        finger_id = int(payload["finger_id"])
    except (TypeError, ValueError):
        return jsonify({"error": "finger_id must be an integer"}), 400

    conn = sqlite3.connect(DB_PATH)
    person = conn.execute("SELECT id, name FROM people WHERE finger_id = ?", (finger_id,)).fetchone()
    if not person:
        conn.close()
        return jsonify({"matched": False, "error": "unknown fingerprint"}), 404

    person_id, name = person
    location, lat, lon = resolve_location(payload, request)
    action = payload.get("action", "check_in")

    now = datetime.now()
    today = date.today().isoformat()
    timestamp = now.isoformat(timespec="seconds")
    window_start = now - timedelta(minutes=DUP_WINDOW_MIN)

    last = conn.execute(
        "SELECT ts FROM attendance WHERE person_id = ? ORDER BY ts DESC LIMIT 1",
        (person_id,),
    ).fetchone()

    if last:
        try:
            last_ts = datetime.fromisoformat(last[0])
        except ValueError:
            last_ts = None
        if last_ts and last_ts >= window_start:
            conn.close()
            return jsonify({
                "matched": True,
                "duplicate": True,
                "name": name,
                "next_allowed_after": (last_ts + timedelta(minutes=DUP_WINDOW_MIN)).isoformat(timespec="seconds")
            })

    if action == "check_out":
        existing = conn.execute(
            "SELECT id FROM attendance WHERE person_id = ? AND day = ?",
            (person_id, today),
        ).fetchone()
        if not existing:
            conn.close()
            return jsonify({"error": "No check-in found for today, please check in first."}), 400
        conn.execute(
            "UPDATE attendance SET check_out_ts = ?, location = ?, lat = ?, lon = ? WHERE person_id = ? AND day = ?",
            (timestamp, location, lat, lon, person_id, today),
        )
    else:
        conn.execute(
            """
            INSERT INTO attendance(person_id, ts, day, location, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(person_id, day) DO UPDATE SET 
                location=excluded.location,
                lat=excluded.lat,
                lon=excluded.lon
            """,
            (person_id, timestamp, today, location, lat, lon),
        )

    conn.commit()
    conn.close()

    return jsonify({
        "matched": True,
        "name": name,
        "timestamp": timestamp,
        "location": location,
        "lat": lat,
        "lon": lon,
        "action": action
    })


@app.route("/api/recognize", methods=["POST"])
def recognize():
    payload = request.get_json()
    if not payload or "image" not in payload:
        return jsonify({"error": "image field is required"}), 400

    if not known_faces:
        return jsonify({"error": "no enrolled faces"}), 400

    image_bgr = decode_image(payload["image"])
    if image_bgr is None:
        return jsonify({"error": "could not decode image"}), 400

    rgb = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2RGB)
    encodings = face_recognition.face_encodings(rgb)
    if not encodings:
        return jsonify({"error": "No face detected."}), 400
        
    if len(encodings) > 1:
        return jsonify({"error": "Multiple people detected. Please ensure only one person is in the frame."}), 400

    encoding = encodings[0]
    known_ids, known_names, known_encs = zip(*known_faces)
    distances = face_recognition.face_distance(known_encs, encoding)
    best_idx = int(np.argmin(distances))
    best_distance = float(distances[best_idx])

    if best_distance > MATCH_THRESHOLD:
        return jsonify({"matched": False, "distance": best_distance}), 404

    person_id = known_ids[best_idx]
    name = known_names[best_idx]

    # Merge client-provided coordinates with server fallbacks/IP lookup
    location, lat, lon = resolve_location(payload, request)
    action = payload.get("action", "check_in")

    now = datetime.now()
    today = date.today().isoformat()
    timestamp = now.isoformat(timespec="seconds")
    window_start = now - timedelta(minutes=DUP_WINDOW_MIN)

    conn = sqlite3.connect(DB_PATH)
    last = conn.execute(
        "SELECT ts FROM attendance WHERE person_id = ? ORDER BY ts DESC LIMIT 1",
        (person_id,),
    ).fetchone()

    if last:
        try:
            last_ts = datetime.fromisoformat(last[0])
        except ValueError:
            last_ts = None
        if last_ts and last_ts >= window_start:
            conn.close()
            return jsonify({
                "matched": True,
                "duplicate": True,
                "name": name,
                "next_allowed_after": (last_ts + timedelta(minutes=DUP_WINDOW_MIN)).isoformat(timespec="seconds")
            })
    
    if action == "check_out":
        # Check if checked in today
        check = conn.execute(
            "SELECT id FROM attendance WHERE person_id = ? AND day = ?", (person_id, today)
        ).fetchone()
        if not check:
            conn.close()
            return jsonify({"error": "No check-in found for today, please check in first."}), 400
        conn.execute(
            "UPDATE attendance SET check_out_ts = ?, location = ?, lat = ?, lon = ? WHERE person_id = ? AND day = ?",
            (timestamp, location, lat, lon, person_id, today),
        )
    else:
        conn.execute(
            """
            INSERT INTO attendance(person_id, ts, day, location, lat, lon)
            VALUES (?, ?, ?, ?, ?, ?)
            ON CONFLICT(person_id, day) DO UPDATE SET 
                location=excluded.location,
                lat=excluded.lat,
                lon=excluded.lon
            """,
            (person_id, timestamp, today, location, lat, lon),
        )
    
    conn.commit()
    conn.close()

    return jsonify({
        "matched": True,
        "name": name,
        "distance": best_distance,
        "timestamp": timestamp,
        "location": location,
        "lat": lat,
        "lon": lon,
        "action": action
    })


@app.route("/api/attendance", methods=["GET"])
def attendance():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT a.ts, p.name, a.location, a.lat, a.lon, a.check_out_ts
        FROM attendance a
        JOIN people p ON a.person_id = p.id
        ORDER BY a.ts DESC
        """
    ).fetchall()
    conn.close()
    return jsonify([
        {
            "name": row[1],
            "timestamp": row[0],
            "location": row[2] or "Unknown Location",
            "lat": row[3],
            "lon": row[4],
            "checkout": row[5]
        } 
        for row in rows
    ])


@app.route("/api/export", methods=["GET"])
def export_csv():
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute(
        """
        SELECT p.name, a.ts, a.check_out_ts, a.day, a.location, a.lat, a.lon
        FROM attendance a
        JOIN people p ON a.person_id = p.id
        ORDER BY a.ts DESC
        """
    ).fetchall()
    conn.close()
    
    si = io.StringIO()
    cw = csv.writer(si)
    cw.writerow(["Name", "Check-in Time", "Check-out Time", "Date", "Location", "Latitude", "Longitude"])
    for r in rows:
        cw.writerow([
            r[0],
            r[1],
            r[2] if r[2] else "--",
            r[3],
            r[4] or "Unknown Location",
            r[5] if r[5] is not None else "",
            r[6] if r[6] is not None else ""
        ])
        
    output = io.BytesIO()
    output.write(si.getvalue().encode('utf-8'))
    output.seek(0)
    return send_file(output, mimetype="text/csv", as_attachment=True, download_name=f"attendance_{date.today().isoformat()}.csv")


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


def startup():
    ensure_db()
    global known_faces
    known_faces = fetch_known_encodings()


startup()


def find_free_port(start_port: int, attempts: int = 10, host: str = "127.0.0.1") -> int:
    """Find an available TCP port starting at start_port.

    In restricted sandboxes socket.bind can raise PermissionError; in that case
    we simply return the preferred port and let app.run handle the error so the
    message is clearer.
    """

    for port in range(start_port, start_port + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                sock.bind((host, port))
                return sock.getsockname()[1]
            except PermissionError:
                # Sandbox / policy blocks binding entirely; defer to app.run for messaging
                return start_port
            except OSError:
                continue

    # If all attempts fail, fall back to the requested port and let app.run decide
    return start_port


if __name__ == "__main__":
    preferred_port = int(os.environ.get("PORT", 5000))
    preferred_host = os.environ.get("HOST", "127.0.0.1")
    try:
        port = find_free_port(preferred_port, host=preferred_host)
    except RuntimeError as err:
        print("Unable to open a local port; check OS permissions or sandboxing.")
        raise err

    if port != preferred_port:
        print(f"Port {preferred_port} is busy; using {port} instead.")

    try:
        app.run(host=preferred_host, port=port, debug=False)
    except OSError as err:
        print(f"Failed to start server on {preferred_host}:{port} -> {err}")
        print("Networking may be blocked in this environment. Try a different HOST/PORT or run outside the sandbox.")
        sys.exit(1)
