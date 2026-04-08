import webview
import threading
from attendance_app import app, find_free_port

def start_server(port):
    # Running Flask with use_reloader=False to avoid running the app twice in threads
    app.run(host='127.0.0.1', port=port, debug=False, use_reloader=False)

if __name__ == '__main__':
    try:
        # We start on port 8000, if not available, grab an available one
        port = find_free_port(8000)
    except RuntimeError:
        port = 8000

    # Start the Flask app gracefully in a background daemon thread
    t = threading.Thread(target=start_server, args=(port,))
    t.daemon = True
    t.start()

    # Create the macOS desktop window container!
    window = webview.create_window(
        title='Smart Attendance',
        url=f'http://localhost:{port}',
        width=1100,
        height=850,
        min_size=(900, 600)
    )

    # Launch Pywebview wrapped desktop GUI
    webview.start(private_mode=False)
