# Smart Attendance System

A simple attendance system that uses geolocation and QR codes to verify student attendance.

## Features

- Professor can create attendance sessions with location and boundary radius
- QR code generation for session details
- Student attendance verification using geolocation
- Automatic attendance marking based on distance from professor
- Mobile-friendly interface

## Setup

1. Create a virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. Install dependencies:
```bash
pip install -r requirements.txt
```

3. Run the application:
```bash
python app.py
```

4. Access the application:
- Professor Dashboard: http://localhost:5000/professor.html
- Student Verification: http://localhost:5000/student.html

## Usage

### Professor Dashboard
1. Open the professor dashboard
2. Enter your current latitude, longitude, and boundary radius
3. Click "Generate Session"
4. Share the generated QR code with students

### Student Verification
1. Open the student verification page
2. Scan the QR code and paste the session data
3. Enter your student ID
4. Click "Verify Attendance"
5. Allow location access when prompted
6. View your attendance status

## Security Notes
- The MVP uses a simple authentication token ("professor_secret")
- Session data is stored in memory (will be lost on server restart)
- In a production environment, consider:
  - Using proper authentication
  - Storing session data in a database
  - Implementing HTTPS
  - Adding rate limiting
  - Using environment variables for sensitive data

## Dependencies
- Flask
- Flask-CORS
- QRCode
- Geopy
- Python-dotenv 