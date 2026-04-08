# 🎓 Smart Attendance System

> An intelligent, automated attendance management system using **Face Recognition** built with Python — developed as a Final Year Project.

---

## 📌 Table of Contents

- Project Overview
- Features
- System Architecture
- Tech Stack
- Project Structure
- Prerequisites
- Installation & Setup
- Usage
- Database Schema
- Screenshots
- Future Enhancements
- Contributors
- License
---

## 📖 Project Overview

The **Smart Attendance System** is a Python-based desktop/web application that automates student or employee attendance using **real-time face recognition** via a webcam. It eliminates the need for manual roll calls, proxy attendance, and paper-based registers.

When a recognized face is detected, the system automatically marks the person as present and logs the timestamp into a local SQLite database (`attendance.db`). Administrators can view, export, and manage attendance records through a simple interface.

---

## ✨ Features

| Feature | Description |
|---|---|
| 🤖 Face Recognition | Automatically identifies registered individuals via webcam |
| 📅 Auto Attendance | Marks attendance with date and timestamp on detection |
| 🗄️ SQLite Database | Lightweight local database for storing records |
| 🧑‍💼 Student/Employee Registration | Register new users with their face encodings |
| 📊 Attendance Reports | View, filter, and export attendance logs |
| ⚠️ Duplicate Prevention | Prevents marking attendance more than once per session |
| 🖥️ GUI Interface | User-friendly interface for easy operation |
| 📁 Export to CSV | Download attendance reports as spreadsheets |

---

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────┐
│                   Smart Attendance System            │
│                                                     │
│  ┌───────────┐    ┌──────────────┐   ┌───────────┐  │
│  │  Webcam   │───▶│ Face Detect  │──▶│   Face    │  │
│  │  Input    │    │  (OpenCV)    │   │  Encode   │  │
│  └───────────┘    └──────────────┘   └─────┬─────┘  │
│                                            │         │
│                                     ┌──────▼──────┐  │
│                                     │  Face Match │  │
│                                     │ (face_recog)│  │
│                                     └──────┬──────┘  │
│                                            │         │
│                          ┌─────────────────▼──────┐  │
│                          │   SQLite Database       │  │
│                          │   (attendance.db)       │  │
│                          └─────────────────────────┘  │
│                                                     │
│  ┌─────────────────────────────────────────────┐    │
│  │              Admin Dashboard                │    │
│  │  (View Reports | Register Users | Export)   │    │
│  └─────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────┘
```

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10+ |
| Face Detection | OpenCV (`cv2`) |
| Face Recognition | `face_recognition` (dlib-based) |
| Database | SQLite3 |
| GUI | Tkinter / PyQt5 |
| Data Handling | Pandas |
| Export | CSV / openpyxl |
| Environment | Python Virtual Environment (`.venv`) |

---

## 📁 Project Structure

```
smart_attendance_project/
│
├── main3.py                  # Main entry point of the application
├── attendance.db             # SQLite database (auto-created on first run)
├── requirements.txt          # Python dependencies
│
├── face_data/                # Stored face encodings for registered users
│   ├── student_001.pkl
│   └── ...
│
├── models/                   # Pre-trained models (if any)
│
├── utils/
│   ├── face_utils.py         # Face detection and encoding helpers
│   ├── db_utils.py           # Database read/write operations
│   └── report_utils.py       # Report generation and CSV export
│
├── gui/
│   ├── main_window.py        # Main GUI window
│   ├── register_window.py    # User registration screen
│   └── report_window.py      # Attendance report screen
│
├── exports/                  # Exported CSV attendance reports
│
└── .venv/                    # Python virtual environment (not committed)
```

---

## ✅ Prerequisites

Make sure you have the following installed before running the project:

- **Python 3.10+** — [Download here](https://www.python.org/downloads/)
- **pip** — comes with Python
- **CMake** — required for building `dlib`
- **A working webcam**

### Install CMake (if not installed)

```bash
# macOS
brew install cmake

# Ubuntu/Debian
sudo apt-get install cmake

# Windows
# Download from https://cmake.org/download/
```

---

## ⚙️ Installation & Setup

### 1. Clone the Repository

```bash
git clone https://github.com/yourusername/smart-attendance-system.git
cd smart-attendance-system
```

### 2. Create and Activate Virtual Environment

```bash
# Create virtual environment
python -m venv .venv

# Activate — macOS/Linux
source .venv/bin/activate

# Activate — Windows
.venv\Scripts\activate
```

### 3. Install Dependencies

```bash
pip install -r requirements.txt
```

> ⚠️ Installing `dlib` and `face_recognition` may take a few minutes. Ensure CMake is installed.

### 4. Run the Application

```bash
python main3.py
```

The SQLite database (`attendance.db`) will be **automatically created** on first launch.

---

## 🚀 Usage

### Registering a New Student/Employee

1. Launch the application with `python main3.py`
2. Click **"Register New User"**
3. Enter the name and ID
4. Look into the webcam — the system captures and saves your face encoding
5. Click **"Save"** — the user is now registered

### Marking Attendance

1. Click **"Start Attendance"**
2. The webcam activates and begins scanning for faces
3. When a registered face is detected, attendance is marked automatically with the current timestamp
4. A confirmation message is displayed on screen

### Viewing Attendance Reports

1. Click **"View Reports"**
2. Filter by date, subject, or student name
3. Export to CSV by clicking **"Export"**

---

## 🗄️ Database Schema

The SQLite database (`attendance.db`) contains the following tables:

### `students` Table

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER (PK) | Auto-incremented student ID |
| `name` | TEXT | Full name of the student |
| `roll_no` | TEXT | Unique roll/employee number |
| `face_encoding` | BLOB | Stored face encoding (binary) |
| `registered_at` | DATETIME | Registration timestamp |

### `attendance` Table

| Column | Type | Description |
|---|---|---|
| `id` | INTEGER (PK) | Auto-incremented record ID |
| `student_id` | INTEGER (FK) | References `students.id` |
| `date` | DATE | Date of attendance |
| `time` | TIME | Time of check-in |
| `status` | TEXT | `Present` / `Absent` |
| `subject` | TEXT | Subject/session name (optional) |

---

## 🔮 Future Enhancements

- [ ] **Web Interface** — Migrate GUI to a Flask/Django web app
- [ ] **Multi-camera Support** — Support for multiple entry points
- [ ] **Liveness Detection** — Prevent spoofing with photos
- [ ] **Mobile App** — Android/iOS companion for reports
- [ ] **Email Alerts** — Notify students/parents of absenteeism
- [ ] **Cloud Database** — Replace SQLite with PostgreSQL or Firebase
- [ ] **Mask Detection** — Recognize faces with masks using deep learning
- [ ] **QR Code Fallback** — Alternative attendance via QR if face fails

---

## 👨‍💻 Contributors

| Name | Role |
|---|---|
| Janakiraman | Developer & Project Lead |

> *Developed as a Final Year Project — [Your College Name], [Year]*

---

## 📄 License

This project is licensed under the **MIT License** — see the [LICENSE](LICENSE) file for details.

---

## 🙏 Acknowledgements

- [face_recognition](https://github.com/ageitgey/face_recognition) by Adam Geitgey
- [OpenCV](https://opencv.org/) — Open Source Computer Vision Library
- [dlib](http://dlib.net/) — C++ Machine Learning Library

---

*Made with ❤️ for automating attendance, one face at a time.*
