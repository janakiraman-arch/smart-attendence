# Smart Attendance System (Face Recognition)

A comprehensive AI-powered attendance system with face recognition, real-time analytics, geolocation tracking, and desktop application support.

## 🚀 Key Features
- **AI Face Recognition**: Automatic check-in using computer vision (OpenCV & face_recognition).
- **Desktop Application**: Native macOS window support via `pywebview`.
- **Analytics Dashboard**: Real-time stats, total enrollments, and daily check-in counts.
- **Geolocation Tracking**: Automatically logs the latitude/longitude of setiap check-in.
- **Voice Assistant**: Integrated Text-to-Speech (TTS) for audible feedback on successes and errors.
- **Modern UI**: Clean, responsive "glassmorphism" design with dark mode support.
- **Nginx Proxy Ready**: Pre-configured reverse proxy support.

## 🛠️ Tech Stack
- **Backend**: Python, Flask, SQLite
- **Frontend**: Vanilla JS, CSS3, HTML5 (Web Speech API, Geolocation API)
- **AI/ML**: OpenCV, face_recognition, dlib
- **Desktop**: PyWebView

## 📦 Setup & Installation

### 1. Environment Configuration
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Dependency Note
This project requires `face_recognition_models`. If they are not found, run:
```bash
pip install git+https://github.com/ageitgey/face_recognition_models
```

## 🏃 Running the Application

### Option A: Desktop App (Recommended)
Launch the native macOS application:
```bash
python desktop_app.py
```

### Option B: Web Server Only
Start the Flask server:
```bash
python attendance_app.py
```
Access via browser at `http://localhost:8001` (or `http://localhost:8080` if using Nginx).

## 📂 Project Structure
- `attendance_app.py`: Core Flask backend & API logic.
- `desktop_app.py`: MacOS desktop window wrapper.
- `static/`: Frontend assets (JavaScript, CSS).
- `templates/`: HTML structures (Dashboard, Camera View).
- `attendance.db`: Local SQLite storage (auto-generated).

## 📝 License
Created for educational and professional face recognition implementations.
