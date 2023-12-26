from fastapi import FastAPI, File, UploadFile, HTTPException, Body, Form
from fastapi.responses import JSONResponse
from typing import List
from datetime import datetime, timedelta
import face_recognition
import firebase_admin
from firebase_admin import credentials, firestore,storage
import os
from pydantic import BaseModel
from pytz import utc
# Initialize Firebase Admin
cred = credentials.Certificate("./firebase.json")
firebase_admin.initialize_app(cred,{"storageBucket": "video-sum-b43b5.appspot.com",})
db = firestore.client()

# FastAPI app instance
app = FastAPI()

# Local storage for quick checks (you can also implement cache for this)
last_check_in = {}

class CheckInRequest(BaseModel):
    name: str
    personId: str
    timestamp: datetime

# Routes
@app.post("/checkin")
async def check_in(check_in_data: CheckInRequest):
    name = check_in_data.name
    personId = check_in_data.personId
    timestamp = check_in_data.timestamp

    # Ensure the timestamp is offset-naive (UTC) for comparison
    timestamp_naive = timestamp.replace(tzinfo=None)

    # Create a composite ID for the document based on personId and the hour of check-in
    doc_id = f"{timestamp_naive.strftime('%Y%m%d')}" # Save this into Month-Day

    try:
        # Try to get the existing document for this hour
        doc_ref = db.collection('attendance').document(doc_id)
        doc = doc_ref.get()
        if doc.exists:
            # If the document exists, check the timestamp to ensure it's not within the last hour
            last_check_in_time = doc.to_dict()['timestamp']
            # Ensure last_check_in_time is offset-naive (UTC) for comparison
            last_check_in_time_naive = last_check_in_time.replace(tzinfo=None)

            if last_check_in_time_naive > timestamp_naive - timedelta(hours=1):
                valid_check_in_time = last_check_in_time_naive + timedelta(hours=1)
                return JSONResponse(
                    content={
                        "error": "You have already checked in recently.",
                        "isChecked": True,
                        "nextValidCheckIn": valid_check_in_time.isoformat()  # ISO format for the valid check-in time
                    },
                    status_code=400
                )

        # If the document doesn't exist or the last check-in was more than an hour ago, set the new check-in
        doc_ref.set({
            'name': name,
            'personId': personId,
            'timestamp': timestamp_naive  # Store as offset-naive
        })

    except Exception as e:
        return JSONResponse(content={"error": f"Failed to save check-in: {e}"}, status_code=500)

    return {"message": "Check-in successful"}

class AttendanceQuery(BaseModel):
    personIds: List[str]  # List of personIds
    startTime: str
    endTime: str

class AttendanceResult(BaseModel):
    name: str
    personId: str
    checkin_times: List[datetime]
    isCheckedFull: bool

def parse_datetime(dt_str):
    # Replace with your actual datetime parsing logic
    return datetime.strptime(dt_str, '%Y-%m-%d %H:%M:%S')

@app.post("/check-attendance", response_model=List[AttendanceResult])
async def check_attendance(query: AttendanceQuery = Body(...)):
    results = []
    start_time = parse_datetime(query.startTime)
    end_time = parse_datetime(query.endTime)
    try:
        for personId in query.personIds:
            # Fetch attendance records from Firestore
            records = db.collection('attendance')\
                .where('personId', '==', personId)\
                .where('timestamp', '>=', start_time)\
                .where('timestamp', '<=', end_time)\
                .stream()

            checkin_times = []
            person_name = 'Unknown'  # Default name if not found in the records
            for record in records:
                data = record.to_dict()
                time = data['timestamp']
                # Convert Firestore timestamp to offset-naive datetime for comparison
                time_naive = time.replace(tzinfo=None)
                checkin_times.append(time_naive)
                # Assume 'name' field exists in the records, adjust as necessary
                if 'name' in data:
                    person_name = data['name']

            checkin_times.sort()  # Ensure times are in chronological order
            isCheckedFull = False
            if len(checkin_times) >= 2:
                earliest = checkin_times[0]
                latest = checkin_times[-1]
                # Check if the earliest and latest check-ins are within 10 minutes of the start and end times
                if (earliest >= start_time - timedelta(minutes=10) and
                        earliest <= start_time + timedelta(minutes=10) and
                        latest >= end_time - timedelta(minutes=10) and
                        latest <= end_time + timedelta(minutes=10)):
                    isCheckedFull = True

            # Append the result for this person
            results.append(AttendanceResult(
                name=person_name,
                personId=personId,
                checkin_times=checkin_times,
                isCheckedFull=isCheckedFull
            ))

        return results
    
    except Exception as e:
        return JSONResponse(content={"error": f"Failed to request: {e}"}, status_code=500)

@app.post("/register")
async def register(name: str = Form(...), personId: str = Form(...), file: UploadFile = File(...)):
    # Ensure the ./images directory exists
    os.makedirs("./images", exist_ok=True)
    
    filename = f"{name} - {personId}.jpg"
    file_path = os.path.join("./images", filename)

    try:
        # Save the image
        with open(file_path, 'wb') as image:
            content = await file.read()  # async read
            image.write(content)
        # Upload the file to Firebase Storage
        bucket = storage.bucket()
        blob = bucket.blob(filename)
        blob.upload_from_filename(file_path)

        # Get the download URL of the uploaded file
        download_url = blob.public_url

        # Store information in Firestore
        db = firestore.client()
        user_ref = db.collection('users').document(personId)
        user_ref.set({
            'name': name,
            'personId': personId,
            'url': download_url,
        })
        # Process and store the face encoding (optional, depending on your use case)
        current_image = face_recognition.load_image_file(file_path)
        encodings = face_recognition.face_encodings(current_image)
        if encodings:
            # You can store these encodings in Firestore or another database for quick access
            pass

        return {"message": f"User {name} registered successfully with ID {personId}"}

    except Exception as e:
        return JSONResponse(content={"error": f"Failed to register user: {e}"}, status_code=500)
@app.get("/get_users")
async def get_users():
    try:
        db = firestore.client()
        users_ref = db.collection('users')

        # Get all documents in the "users" collection
        users = users_ref.stream()

        # Extract data from each document
        result = []
        for user in users:
            user_data = user.to_dict()
            result.append(user_data)

        return result

    except Exception as e:
        return JSONResponse(content={"error": f"Failed to get user: {e}"}, status_code=500)

@app.delete("/delete_user/")
async def delete_user(name: str, personId: str):
    try:
        db = firestore.client()
        users_ref = db.collection('users')
        query = users_ref.where('personId', '==', personId).stream()
        user_doc = next(query, None)
        if user_doc:
            # Get the user data
            user_data = user_doc.to_dict()

            # Delete the user's image from Firebase Storage
            storage_filename = f"{name} - {personId}.jpg"
            bucket = storage.bucket()
            blob = bucket.blob(storage_filename)
            blob.delete()

            # Delete the user document from Firestore
            users_ref.document(personId).delete()

            # Delete the user's image from the local file system
            local_filename = f"{name} - {personId}.jpg"
            local_filepath = os.path.join("./images", local_filename)
            os.remove(local_filepath)

            return {"message": f"User {name} with ID {personId} deleted successfully"}

        else:
            return JSONResponse(content={"error": f"Not found user"}, status_code=404)

    except Exception as e:
        return JSONResponse(content={"error": f"Failed to delete user: {e}"}, status_code=500)
# Run the server
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
