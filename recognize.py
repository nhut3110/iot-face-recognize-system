import face_recognition
import cv2
import os
import numpy as np
from datetime import datetime
import requests
import urllib.request
import serial

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

# URL of the remote camera
url = 'http://172.16.5.59/cam-hi.jpg'

# MSerial
ser = serial.Serial('COM8', 9600)
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

                # Check if we should wait before next check-in attempt
                current_time = datetime.now()
                if personId in next_valid_check_in and next_valid_check_in[personId] > current_time:
                    next_valid = f"Next valid check-in for {name} is at {next_valid_check_in[personId]}"
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
                    success = f'Check-in successful for {name}'
                    ser.write((success + '\n').encode())
                    print(f"Check-in successful for {name}")
                elif response.status_code == 400:
                    response_data = response.json()
                    if response_data.get('isChecked'):
                        failed_check = f"Failed to check in {name}: {response_data.get('error')}"
                        ser.write((failed_check + '\n').encode())
                        print(f"Failed to check in {name}: {response_data.get('error')}")
                        # Update the next valid check-in time
                        next_valid_check_in[personId] = datetime.fromisoformat(response_data['nextValidCheckIn'])
                    else:
                        failed_check = f"Failed to check in {name}: {response_data.get('error')}"
                        ser.write((failed_check + '\n').encode())
                        print(f"Failed to check in {name}: {response_data.get('error')}")
                else:
                    failed_check = f"Failed to check in {name}: {response.status_code} - {response.text}"
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
