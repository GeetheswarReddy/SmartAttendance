from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from supabase import create_client
from datetime import datetime, timedelta, UTC
import geocoder
import qrcode
import os
from dotenv import load_dotenv
from geopy.distance import distance

# Load environment variables
load_dotenv()

# Initialize Flask app
app = Flask(__name__, static_folder='static')
CORS(app)

# Initialize Supabase client
supabase_url = os.environ.get("SUPABASE_URL")
supabase_key = os.environ.get("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

# Serve static files
@app.route('/')
def serve_index():
    return send_from_directory('static', 'index.html')

@app.route('/professor')
def serve_professor():
    return send_from_directory('static', 'professor.html')

@app.route('/student')
def serve_student():
    return send_from_directory('static', 'student.html')

# API Endpoints
@app.route('/get_location', methods=['GET'])
def get_location():
    try:
        g = geocoder.ip('me')
        if g.latlng:
            return jsonify({'lat': g.latlng[0], 'lon': g.latlng[1]})
        return jsonify({'error': 'Could not get location'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/generate_session', methods=['POST'])
def generate_session():
    try:
        # Get auth token from header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'This endpoint requires a Bearer token'}), 401
        
        token = auth_header.split(' ')[1]
        
        # Verify token with Supabase
        user = supabase.auth.get_user(token)
        if not user:
            return jsonify({'error': 'Invalid token'}), 401

        data = request.json
        lat = data.get('lat')
        lon = data.get('lon')
        boundary_radius = data.get('boundary_radius')

        if not all([lat, lon, boundary_radius]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Create session in database
        session_data = {
            'prof_id': user.user.id,
            'prof_location': {'lat': lat, 'lon': lon},
            'boundary_radius': boundary_radius,
            'expiry': (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
        }
        
        result = supabase.table('sessions').insert(session_data).execute()
        session = result.data[0]

        # Generate QR code
        qr = qrcode.QRCode(version=1, box_size=10, border=5)
        qr.add_data(str(session))
        qr.make(fit=True)
        img = qr.make_image(fill_color="black", back_color="white")
        
        # Save QR code
        qr_path = f'static/qr_codes/session_{session["id"]}.png'
        os.makedirs(os.path.dirname(qr_path), exist_ok=True)
        img.save(qr_path)

        return jsonify({
            'session_id': session['id'],
            'qr_code_url': f'/qr_codes/session_{session["id"]}.png',
            'expiry': session['expiry']
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/verify_attendance', methods=['POST'])
def verify_attendance():
    try:
        # Get auth token from header
        auth_header = request.headers.get('Authorization')
        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'error': 'This endpoint requires a Bearer token'}), 401
        
        token = auth_header.split(' ')[1]
        
        # Verify token with Supabase
        user = supabase.auth.get_user(token)
        if not user:
            return jsonify({'error': 'Invalid token'}), 401

        data = request.json
        session_data = data.get('session_data')
        student_location = data.get('student_location')

        if not all([session_data, student_location]):
            return jsonify({'error': 'Missing required fields'}), 400

        # Get session from database
        session = supabase.table('sessions').select('*').eq('id', session_data['id']).execute()
        if not session.data:
            return jsonify({'error': 'Session not found'}), 404

        session = session.data[0]

        # Check if session is expired
        if datetime.fromisoformat(session['expiry']) < datetime.now(UTC):
            return jsonify({'error': 'Session has expired'}), 400

        # Calculate distance
        prof_location = session['prof_location']
        dist = distance(
            (prof_location['lat'], prof_location['lon']),
            (student_location['lat'], student_location['lon'])
        ).meters

        # Determine attendance status
        status = 'present' if dist <= session['boundary_radius'] else 'absent'

        # Record attendance
        attendance_data = {
            'session_id': session['id'],
            'student_id': user.user.id,
            'student_location': student_location,
            'distance': dist,
            'status': status
        }
        
        supabase.table('attendance').insert(attendance_data).execute()

        return jsonify({
            'status': status,
            'distance': dist,
            'timestamp': datetime.now(UTC).isoformat()
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True) 