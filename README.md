# Face Recognition Attendance System - Backend

## Introduction
This project focuses on implementing a facial recognition-based attendance system with backend support. The system utilizes Firebase for data storage and provides flexibility to switch databases by configuring the `firebase.json` file. The project includes a Postman collection (`face.postman_collection.json`) for convenient API testing.

## Setup

1. Install required libraries using the following command:
    ```bash
    pip install -r requirements.txt
    ```

2. Run the API using the main script:
    ```bash
    python -m uvicorn main:app --reload
    ```

## Face Recognition Setup

1. Adjust the ESP32 camera URL in the `recognize.py` file:
    ```python
    # URL of the remote camera
    url = 'http://your_esp32_ip_address/cam-mid.jpg'
    ```

2. Configure the Arduino COM port in the `recognize.py` file:
    ```python
    # Serial connection
    ser = serial.Serial('COM5', 9600)
    ```

3. Run the face recognition script:
    ```bash
    python recognize.py
    ```

## Additional Notes
- Ensure that Firebase configurations in `firebase.json` are accurate.
- Make sure to have a reliable internet connection for Firebase operations.
- The project assumes ESP32 camera integration. Adjust the ESP32 camera URL accordingly.

## API Endpoints
Refer to the Postman collection (`face.postman_collection.json`) for detailed API documentation and testing.

Feel free to reach out for any issues or improvements. Happy coding!