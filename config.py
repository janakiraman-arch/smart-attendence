# config.py

# Drowsiness detection parameters
EAR_THRESHOLD = 0.25  # Eye Aspect Ratio threshold (below this is closed)
EAR_CONSEC_FRAMES = 20  # Number of consecutive frames eyes must be closed to trigger alarm

# Distraction detection parameters (Head Pose)
# Angles in degrees
YAW_THRESHOLD_LEFT = -20
YAW_THRESHOLD_RIGHT = 20
PITCH_THRESHOLD_DOWN = -15
PITCH_THRESHOLD_UP = 20

# Colors (B, G, R)
COLOR_GREEN = (0, 255, 0)
COLOR_RED = (0, 0, 255)
COLOR_YELLOW = (0, 255, 255)
COLOR_WHITE = (255, 255, 255)

# Text Settings
FONT_SCALE = 0.7
FONT_THICKNESS = 2

# Alarm Sound Path
ALARM_PATH = "assets/alarm.wav"
