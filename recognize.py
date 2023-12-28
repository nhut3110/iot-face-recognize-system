import face_recognition
import cv2
import os
import numpy as np
from datetime import datetime, timedelta
import requests
import urllib.request
import serial
import time

# Load images and create encodings
def load_images_from_folder(folder='./images'):
    images = {}
    for filename in os.listdir(folder):
        if filename.endswith(".jpg") or filename.endswith(".png"):
            path = os.path.join(folder, filename)
            image = face_recognition.load_image_file(path)
            encodings = face_recognition.face_encodings(image)
            if encodings:
                images[filename.split('.')[0]] = encodings[0]
    return images

# Initialize some variables
known_faces = load_images_from_folder()
next_valid_check_in = {}  # Keep track of next valid check-in time for each person
continuous_seen = {}  # Track the last time a person was continuously seen
seen_count = {}  # Count how long a person has been continuously seen
recognition_tolerance = 0.35  # Define the tolerance for face recognition (lower is more strict)

# URL of the remote camera
url = 'http://172.16.4.25/cam-mid.jpg'

# MSerial
ser = serial.Serial('COM5', 9600)

while True:
    try:
        img_resp = urllib.request.urlopen(url)
        imgnp = np.array(bytearray(img_resp.read()), dtype=np.uint8)
        frame = cv2.imdecode(imgnp, -1)

        if frame is None:
            print("Failed to grab frame from IP camera")
            continue

        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        current_time = datetime.now()

        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding)
            face_distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
            best_match_index = np.argmin(face_distances)
            
            print(f"Tolerance accepted: {face_distances[best_match_index]}")

            if matches[best_match_index] and face_distances[best_match_index] < recognition_tolerance:
                image_name = list(known_faces.keys())[best_match_index]
                name, personId = image_name.split('-')
                name = name.strip()
                personId = personId.strip()

                if personId not in continuous_seen:
                    continuous_seen[personId] = current_time
                    seen_count[personId] = 0

                if current_time - continuous_seen[personId] < timedelta(seconds=5):
                    seen_count[personId] += 1
                    if seen_count[personId] < 5:
                        scanning = f"{name}..."
                        ser.write((scanning + '\n').encode())
                        print(f"Waiting for {name} to stay in view...")
                        continue

                seen_count[personId] = 0
                continuous_seen[personId] = current_time

                if personId in next_valid_check_in and next_valid_check_in[personId] > current_time:
                    next_valid = f"Back at {next_valid_check_in[personId].strftime('%H:%M')}"
                    ser.write((next_valid + '\n').encode())
                    print(f"Next valid check-in for {name} is at {next_valid_check_in[personId]}")
                    continue

                payload = {
                    'name': name,
                    'personId': personId,
                    'timestamp': current_time.isoformat()
                }
                response = requests.post('http://127.0.0.1:8000/checkin', json=payload)

                if response.status_code == 200:
                    success = f'Check-in {name}'
                    ser.write((success + '\n').encode())
                    print(f"Check-in successful for {name}")
                elif response.status_code == 400:
                    response_data = response.json()
                    if response_data.get('isChecked'):
                        failed_check = f"Checkin already {name}"
                        ser.write((failed_check + '\n').encode())
                        print(f"Failed to check in {name}: {response_data.get('error')}")
                        next_valid_check_in[personId] = datetime.fromisoformat(response_data['nextValidCheckIn'])
                    else:
                        failed_check = f"Checkin failed {name}"
                        ser.write((failed_check + '\n').encode())
                        print(f"Failed to check in {name}: {response_data.get('error')}")
                else:
                    failed_check = f"Checkin failed {name}"
                    ser.write((failed_check + '\n').encode())
                    print(f"Failed to check in {name}: {response.status_code} - {response.text}")
            else:
                # If no match is found or the best match is too far, treat as unknown.
                unknown_message = "Unknown face detected"
                ser.write((unknown_message + '\n').encode())
                print(unknown_message)

        cv2.imshow('Video', frame)

        if cv2.waitKey(10) & 0xFF == ord('q'):
            break
    except Exception as e:
        print(f"An error occurred: {e}")

cv2.destroyAllWindows()
