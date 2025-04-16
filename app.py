from flask import Flask, request, jsonify, send_file, send_from_directory
from flask_cors import CORS
import qrcode
import io
import uuid
# Update the datetime import at the top of the file
from datetime import datetime, timedelta, UTC
from geopy.distance import distance
import json
from database import (
    create_session, get_session, record_attendance,
    get_current_location, get_user_role, get_user_sessions
)
import os
from supabase import create_client
from dotenv import load_dotenv
import jwt
from io import BytesIO
import geocoder

# Load environment variables
load_dotenv()

app = Flask(__name__, static_folder='.')
CORS(app, resources={
    r"/*": {
        "origins": ["http://127.0.0.1:5000"],
        "methods": ["GET", "POST", "OPTIONS"],
        "allow_headers": ["Content-Type", "Authorization"]
    }
})

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

def verify_token(token):
    try:
        # Print token for debugging
        print("Verifying token:", token)
        
        # Verify the token with Supabase
        response = supabase.auth.get_user(token)
        print("Supabase auth response:", response)
        
        if not response or not response.user:
            print("No user data in response")
            return False, None
            
        print("User verified:", response.user)
        return True, response
    except Exception as e:
        print("Token verification failed:", str(e))
        print("Full error details:", {
            'error_type': type(e).__name__,
            'error_message': str(e),
            'token_length': len(token) if token else 0
        })
        return False, None

@app.route('/')
def index():
    return send_from_directory('.', 'login.html')

@app.route('/professor.html')
def professor():
    return send_from_directory('.', 'professor.html')

@app.route('/student.html')
def student():
    return send_from_directory('.', 'student.html')

@app.route('/professor.css')
def professor_css():
    return send_from_directory('.', 'professor.css')

@app.route('/student.css')
def student_css():
    return send_from_directory('.', 'student.css')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    try:
        response = supabase.auth.sign_in_with_password({
            "email": email,
            "password": password
        })
        
        # Convert AuthResponse to a dictionary with needed data
        return jsonify({
            'session': {
                'access_token': response.session.access_token,
                'expires_at': response.session.expires_at,
                'refresh_token': response.session.refresh_token
            },
            'user': {
                'id': response.user.id,
                'email': response.user.email
            }
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 401

@app.route('/get_location', methods=['GET'])
def get_location():
    try:
        # Return empty response to trigger client-side location
        return jsonify({'message': 'Use client location'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate_session', methods=['POST'])
def generate_session():
    # Get the authorization header
    auth_header = request.headers.get('Authorization')
    print("Received headers:", dict(request.headers))
    print("Auth header:", auth_header)

    if not auth_header:
        return jsonify({'error': 'No Authorization header'}), 401

    if not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Invalid Authorization header format'}), 401

    token = auth_header.split(' ')[1]
    print("Extracted token:", token)

    try:
        # Verify the token with Supabase
        response = supabase.auth.get_user(token)
        print("Supabase auth response:", response)
        
        if not response or not response.user:
            print("No user data in response")
            return jsonify({'error': 'Invalid token'}), 401
            
        print("User verified:", response.user)
        
        # Get request data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Create session in database
        session_data = {
            'prof_id': response.user.id,  # Use response.user.id
            'prof_location': {'lat': data['lat'], 'lon': data['lon']},
            'boundary_radius': data['boundary_radius'],
            'expiry': (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        }
        
        print("Creating session with data:", session_data)
        
        result = supabase.table('sessions').insert(session_data).execute()
        print("Supabase insert result:", result)
        
        session = result.data[0]

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(str(session['id']))
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")

        # Save QR code
        img_io = BytesIO()
        qr_image.save(img_io, 'PNG')
        img_io.seek(0)

        # Return session data with QR code URL
        return jsonify({
            'session_id': session['id'],
            'qr_code_url': f'/get_qr/{session["id"]}',
            'expiry': session['expiry']
        })

    except Exception as e:
        print("Error creating session. Full error:", str(e))
        return jsonify({'error': str(e)}), 500

@app.route('/get_qr/<session_id>', methods=['GET'])
def get_qr(session_id):
    try:
        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(session_id)
        qr.make(fit=True)
        qr_image = qr.make_image(fill_color="black", back_color="white")

        # Save QR code to BytesIO
        img_io = BytesIO()
        qr_image.save(img_io, 'PNG')
        img_io.seek(0)

        return send_file(img_io, mimetype='image/png')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify_attendance', methods=['POST'])
def verify_attendance():
    # Get user from session
    auth_header = request.headers.get('Authorization')
    if not auth_header:
        return jsonify({'error': 'No authorization header'}), 401

    try:
        # Extract Bearer token
        if not auth_header.startswith('Bearer '):
            return jsonify({'error': 'Invalid token format'}), 401
            
        token = auth_header.split(' ')[1]
        
        # Verify token with Supabase
        user = supabase.auth.get_user(token)
        student_id = user.user.id

        # Parse JSON data
        data = request.get_json()
        if not data:
            return jsonify({'error': 'Invalid JSON data'}), 400

        session_id = data.get('session_data')
        student_location = data.get('student_location')

        if not all([session_id, student_location]):
            return jsonify({'error': 'Missing required fields'}), 400

        session = get_session(session_id)
        if not session:
            return jsonify({'error': 'Invalid session'}), 400

        expiry = datetime.fromisoformat(session['expiry'])
        if datetime.now(UTC) > expiry:
            return jsonify({'error': 'Session expired'}), 400

        # Calculate distance
        prof_loc = session['prof_location']
        dist = distance(
            (prof_loc['lat'], prof_loc['lon']),
            (student_location['lat'], student_location['lon'])
        ).meters

        # Adjust boundary check with more reasonable thresholds
        boundary_radius = float(session['boundary_radius'])
        if dist <= boundary_radius:
            status = 'present'
        elif dist <= boundary_radius * 2:  # Allow some flexibility
            status = 'manual_review'
        else:
            status = 'absent'

        # Record attendance
        attendance = record_attendance(
            session_id=session_id,
            student_id=student_id,
            student_location=student_location,
            distance=dist,
            status=status
        )

        return jsonify({
            'student_id': student_id,
            'session_id': session_id,
            'distance': dist,
            'timestamp': attendance['timestamp'],
            'status': status
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 401

# Add these new routes
@app.route('/login.css')
def login_css():
    return send_from_directory('.', 'login.css')

@app.route('/get_user_role')
def get_user_role():
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return jsonify({'error': 'Invalid token'}), 401
    
    token = auth_header.split(' ')[1]
    try:
        # Get user from Supabase
        user = supabase.auth.get_user(token)
        
        # Get user role from users table
        response = supabase.table('users').select('role').eq('id', user.user.id).execute()
        
        if response.data:
            return jsonify({'role': response.data[0]['role']})
        else:
            # If no role found, default to student
            return jsonify({'role': 'student'})
    except Exception as e:
        print("Error getting user role:", str(e))
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5002, debug=True)