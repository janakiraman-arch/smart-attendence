import cv2
import mediapipe as mp
import numpy as np
import time
import os
import config
from detectors import calculate_EAR, get_head_pose

def main():
    # Initialize MediaPipe Face Mesh
    mp_face_mesh = mp.solutions.face_mesh
    face_mesh = mp_face_mesh.FaceMesh(
        min_detection_confidence=0.5,
        min_tracking_confidence=0.5,
        refine_landmarks=True
    )

    # Initialize Video Capture
    cap = cv2.VideoCapture(0)
    
    # Check if camera opened successfully
    if not cap.isOpened():
        print("Error: Could not open webcam.")
        return

    # Counter for drowsiness
    ear_counter = 0
    
    # Indices for eyes (Subject's Left and Right)
    # Right Eye (User's Left side of face): 33, 160, 158, 133, 153, 144
    RIGHT_EYE_INDICES = [33, 160, 158, 133, 153, 144]
    # Left Eye (User's Right side of face): 362, 385, 387, 263, 373, 380
    LEFT_EYE_INDICES = [362, 385, 387, 263, 373, 380]

    last_alarm_time = 0 
    prev_frame_time = 0
    
    print("Starting Driver Drowsiness Detection... Press 'q' to quit.")

    while cap.isOpened():
        success, image = cap.read()
        if not success:
            print("Ignoring empty camera frame.")
            continue

        # Flip the image horizontally for a later selfie-view display
        # Note: If we flip, left becomes right. MediaPipe assumes unmirrored usually? 
        # Actually MediaPipe works on the image as is. If we flip for display, we must be careful with 'Left/Right' text.
        # Let's flip for display and processing so it feels like a mirror. 
        # BUT MediaPipe landmarks are relative to the image. 
        image = cv2.flip(image, 1)
        
        h, w, _ = image.shape
        rgb_image = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)

        # Process the image
        results = face_mesh.process(rgb_image)

        if results.multi_face_landmarks:
            for face_landmarks in results.multi_face_landmarks:
                # Convert normalized landmarks to pixel coordinates
                mesh_points = []
                for pt in face_landmarks.landmark:
                    x = int(pt.x * w)
                    y = int(pt.y * h)
                    mesh_points.append((x, y))
                
                # --- Drowsiness Detection (EAR) ---
                # Extract eye landmarks
                right_eye = [mesh_points[i] for i in RIGHT_EYE_INDICES]
                left_eye = [mesh_points[i] for i in LEFT_EYE_INDICES]

                # Calculate EAR
                ear_right = calculate_EAR(right_eye)
                ear_left = calculate_EAR(left_eye)
                avg_ear = (ear_right + ear_left) / 2.0

                # Check Threshold
                if avg_ear < config.EAR_THRESHOLD:
                    ear_counter += 1
                else:
                    ear_counter = 0

                # Drowsiness Alert
                if ear_counter >= config.EAR_CONSEC_FRAMES:
                    cv2.putText(image, "DROWSINESS ALERT!", (10, 50),
                                cv2.FONT_HERSHEY_SIMPLEX, config.FONT_SCALE, config.COLOR_RED, config.FONT_THICKNESS)
                    
                    # Play sound (non-blocking, limit frequency)
                    if time.time() - last_alarm_time > 2.0:
                        os.system(f"afplay {config.ALARM_PATH}&")
                        last_alarm_time = time.time()

                # Display EAR
                cv2.putText(image, f"EAR: {avg_ear:.2f}", (10, 30),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, config.COLOR_GREEN, 1)

                # --- Distraction Detection (Head Pose) ---
                pitch, yaw, roll = get_head_pose(mesh_points, w, h)

                distracted = False
                if yaw < config.YAW_THRESHOLD_LEFT:
                    cv2.putText(image, "LOOKING LEFT", (10, 100),
                                cv2.FONT_HERSHEY_SIMPLEX, config.FONT_SCALE, config.COLOR_YELLOW, config.FONT_THICKNESS)
                    distracted = True
                elif yaw > config.YAW_THRESHOLD_RIGHT:
                    cv2.putText(image, "LOOKING RIGHT", (10, 100),
                                cv2.FONT_HERSHEY_SIMPLEX, config.FONT_SCALE, config.COLOR_YELLOW, config.FONT_THICKNESS)
                    distracted = True
                
                if pitch < config.PITCH_THRESHOLD_DOWN:
                    cv2.putText(image, "LOOKING DOWN", (10, 130),
                                cv2.FONT_HERSHEY_SIMPLEX, config.FONT_SCALE, config.COLOR_YELLOW, config.FONT_THICKNESS)
                    distracted = True
                # Optional: Looking UP (often less critical, but can add)
                
                if distracted:
                    cv2.putText(image, "DISTRACTED!", (10, 80),
                                cv2.FONT_HERSHEY_SIMPLEX, config.FONT_SCALE, config.COLOR_RED, config.FONT_THICKNESS)
                    # Use a simpler/shorter beep for distraction if needed, or same alarm
                    if time.time() - last_alarm_time > 2.0:
                        os.system(f"afplay {config.ALARM_PATH}&")
                        last_alarm_time = time.time()

                # Display Head Pose
                cv2.putText(image, f"Pitch: {pitch:.1f} Yaw: {yaw:.1f}", (10, h - 20),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, config.COLOR_WHITE, 1)

        # FPS Counter
        curr_time = time.time()
        fps = 1 / (curr_time - prev_frame_time) if (curr_time - prev_frame_time) > 0 else 0
        prev_frame_time = curr_time
        
        cv2.putText(image, f"FPS: {int(fps)}", (w - 100, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, config.COLOR_GREEN, 2)


        # Show the image
        cv2.imshow('Driver Drowsiness Detection', image)

        # Exit
        if cv2.waitKey(5) & 0xFF == ord('q'):
            break

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()
