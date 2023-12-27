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

# URL of the remote camera
url = 'http://172.16.5.59/cam-mid.jpg'

# MSerial
ser = serial.Serial('COM5', 9600)

while True:
    try:
        # Use urllib to get the image from the IP camera
        img_resp = urllib.request.urlopen(url)
        imgnp = np.array(bytearray(img_resp.read()), dtype=np.uint8)
        frame = cv2.imdecode(imgnp, -1)

        # Check if we got a frame
        if frame is None:
            print("Failed to grab frame from IP camera")
            continue  # Skip the rest of this loop iteration

        # Convert the image from BGR color (which OpenCV uses) to RGB color (which face_recognition uses)
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Find all face locations and face encodings in the current frame
        face_locations = face_recognition.face_locations(rgb_frame)
        face_encodings = face_recognition.face_encodings(rgb_frame, face_locations)

        current_time = datetime.now()

        for face_encoding in face_encodings:
            matches = face_recognition.compare_faces(list(known_faces.values()), face_encoding)
            name = "Unknown"

            # Use the known face with the smallest distance to the new face
            face_distances = face_recognition.face_distance(list(known_faces.values()), face_encoding)
            best_match_index = np.argmin(face_distances)
            if matches[best_match_index]:
                image_name = list(known_faces.keys())[best_match_index]
                name, personId = image_name.split('-')  # Assuming the format is "name - personId"
                name = name.strip()
                personId = personId.strip()

                # Initialize continuous_seen and seen_count for the person if not already present
                if personId not in continuous_seen:
                    continuous_seen[personId] = current_time
                    seen_count[personId] = 0

                # Check if the same user stays at camera continuously for at least 5 seconds
                if current_time - continuous_seen[personId] < timedelta(seconds=5):
                    seen_count[personId] += 1  # Increment seen count
                    if seen_count[personId] < 5:
                        scanning = f"{name}..."
                        ser.write((scanning + '\n').encode())
                        print(f"Waiting for {name} to stay in view...")
                        continue

                # Reset seen count and update last seen time
                seen_count[personId] = 0
                continuous_seen[personId] = current_time

                # Check if we should wait before next check-in attempt
                if personId in next_valid_check_in and next_valid_check_in[personId] > current_time:
                    next_valid = f"Back at {next_valid_check_in[personId].strftime('%H:%M')}"
                    ser.write((next_valid + '\n').encode())
                    print(f"Next valid check-in for {name} is at {next_valid_check_in[personId]}")
                    continue

                # Prepare the payload for the POST request
                payload = {
                    'name': name,
                    'personId': personId,
                    'timestamp': current_time.isoformat()
                }
                response = requests.post('http://127.0.0.1:8000/checkin', json=payload)

                # Handle the response
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
                        # Update the next valid check-in time
                        next_valid_check_in[personId] = datetime.fromisoformat(response_data['nextValidCheckIn'])
                    else:
                        failed_check = f"Checkin failed {name}"
                        ser.write((failed_check + '\n').encode())
                        print(f"Failed to check in {name}: {response_data.get('error')}")
                else:
                    failed_check = f"Checkin failed {name}"
                    ser.write((failed_check + '\n').encode())
                    print(f"Failed to check in {name}: {response.status_code} - {response.text}")

        # Display the resulting image
        cv2.imshow('Video', frame)

        # Wait for a while, press 'q' to quit
        if cv2.waitKey(10) & 0xFF == ord('q'):
            break
    except Exception as e:
        print(f"An error occurred: {e}")

cv2.destroyAllWindows()
