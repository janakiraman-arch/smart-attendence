# detectors.py
import numpy as np
import cv2
from scipy.spatial import distance as dist

def calculate_EAR(eye_landmarks):
    """
    Calculates the Eye Aspect Ratio (EAR).
    EAR = (|p2-p6| + |p3-p5|) / (2 * |p1-p4|)
    where p1..p6 are 2D landmark coordinates.
    """
    # Vertical distances
    A = dist.euclidean(eye_landmarks[1], eye_landmarks[5])
    B = dist.euclidean(eye_landmarks[2], eye_landmarks[4])

    # Horizontal distance
    C = dist.euclidean(eye_landmarks[0], eye_landmarks[3])

    if C == 0:
        return 0.0

    ear = (A + B) / (2.0 * C)
    return ear

def get_head_pose(face_landmarks, img_w, img_h):
    """
    Estimates head pose (pitch, yaw, roll) from 3D face landmarks using PnP.
    """
    # 2D image points (from MediaPipe landmarks)
    # Nose tip, Chin, Left eye left corner, Right eye right corner, Left Mouth corner, Right mouth corner
    image_points = np.array([
        face_landmarks[1],   # Nose tip
        face_landmarks[152], # Chin
        face_landmarks[263], # Left eye left corner
        face_landmarks[33],  # Right eye right corner
        face_landmarks[291], # Left Mouth corner
        face_landmarks[61]   # Right mouth corner
    ], dtype="double")

    # 3D model points (generic face model)
    model_points = np.array([
        (0.0, 0.0, 0.0),             # Nose tip
        (0.0, -330.0, -65.0),        # Chin
        (-225.0, 170.0, -135.0),     # Left eye left corner
        (225.0, 170.0, -135.0),      # Right eye right corner
        (-150.0, -150.0, -125.0),    # Left Mouth corner
        (150.0, -150.0, -125.0)      # Right mouth corner
    ])

    # Camera internals
    focal_length = img_w
    center = (img_w / 2, img_h / 2)
    camera_matrix = np.array(
        [[focal_length, 0, center[0]],
         [0, focal_length, center[1]],
         [0, 0, 1]], dtype="double"
    )
    dist_coeffs = np.zeros((4, 1))  # Assuming no lens distortion for simplicity

    # Solve PnP
    (success, rotation_vector, translation_vector) = cv2.solvePnP(
        model_points, image_points, camera_matrix, dist_coeffs, flags=cv2.SOLVEPNP_ITERATIVE
    )

    if not success:
        return 0, 0, 0

    # Get rotation matrix
    (rotation_matrix, jacobian) = cv2.Rodrigues(rotation_vector)

    # Get angles
    proj_matrix = np.hstack((rotation_matrix, translation_vector))
    eulerAngles = cv2.decomposeProjectionMatrix(proj_matrix)[6]
    
    pitch, yaw, roll = [math_angle for math_angle in eulerAngles.flatten()]
    
    # Pitch: x-axis
    # Yaw: y-axis
    # Roll: z-axis

    return pitch, yaw, roll
