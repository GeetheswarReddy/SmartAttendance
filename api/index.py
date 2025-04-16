from http.server import BaseHTTPRequestHandler
import json
import qrcode
import io
from datetime import datetime, timedelta, UTC
from geopy.distance import distance
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

# Initialize Supabase client
supabase_url = os.getenv("SUPABASE_URL")
supabase_key = os.getenv("SUPABASE_KEY")
supabase = create_client(supabase_url, supabase_key)

def verify_token(token):
    try:
        response = supabase.auth.get_user(token)
        if not response or not response.user:
            return False, None
        return True, response
    except Exception as e:
        return False, None

class handler(BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization')
        self.end_headers()
        return

    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        content_length = int(self.headers['Content-Length'])
        post_data = self.rfile.read(content_length)
        data = json.loads(post_data)

        if self.path == '/api/login':
            try:
                response = supabase.auth.sign_in_with_password({
                    "email": data.get('email'),
                    "password": data.get('password')
                })
                
                self.wfile.write(json.dumps({
                    'session': {
                        'access_token': response.session.access_token,
                        'expires_at': response.session.expires_at,
                        'refresh_token': response.session.refresh_token
                    },
                    'user': {
                        'id': response.user.id,
                        'email': response.user.email
                    }
                }).encode())
            except Exception as e:
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        elif self.path == '/api/generate_session':
            auth_header = self.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                self.wfile.write(json.dumps({'error': 'Invalid token'}).encode())
                return

            token = auth_header.split(' ')[1]
            is_valid, response = verify_token(token)
            
            if not is_valid:
                self.wfile.write(json.dumps({'error': 'Invalid token'}).encode())
                return

            try:
                session_data = {
                    'prof_id': response.user.id,
                    'prof_location': {'lat': data['lat'], 'lon': data['lon']},
                    'boundary_radius': data['boundary_radius'],
                    'expiry': (datetime.now(UTC) + timedelta(minutes=10)).isoformat()
                }
                
                result = supabase.table('sessions').insert(session_data).execute()
                session = result.data[0]

                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(str(session['id']))
                qr.make(fit=True)
                qr_image = qr.make_image(fill_color="black", back_color="white")

                img_io = BytesIO()
                qr_image.save(img_io, 'PNG')
                img_io.seek(0)

                self.wfile.write(json.dumps({
                    'session_id': session['id'],
                    'qr_code_url': f'/api/get_qr/{session["id"]}',
                    'expiry': session['expiry']
                }).encode())

            except Exception as e:
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        elif self.path.startswith('/api/get_qr/'):
            session_id = self.path.split('/')[-1]
            try:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(session_id)
                qr.make(fit=True)
                qr_image = qr.make_image(fill_color="black", back_color="white")

                img_io = BytesIO()
                qr_image.save(img_io, 'PNG')
                img_io.seek(0)

                self.send_header('Content-type', 'image/png')
                self.end_headers()
                self.wfile.write(img_io.getvalue())

            except Exception as e:
                self.wfile.write(json.dumps({'error': str(e)}).encode())

        elif self.path == '/api/verify_attendance':
            auth_header = self.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                self.wfile.write(json.dumps({'error': 'Invalid token'}).encode())
                return

            token = auth_header.split(' ')[1]
            is_valid, response = verify_token(token)
            
            if not is_valid:
                self.wfile.write(json.dumps({'error': 'Invalid token'}).encode())
                return

            try:
                session_id = data.get('session_data')
                student_location = data.get('student_location')

                session = get_session(session_id)
                if not session:
                    self.wfile.write(json.dumps({'error': 'Invalid session'}).encode())
                    return

                expiry = datetime.fromisoformat(session['expiry'])
                if datetime.now(UTC) > expiry:
                    self.wfile.write(json.dumps({'error': 'Session expired'}).encode())
                    return

                prof_loc = session['prof_location']
                dist = distance(
                    (prof_loc['lat'], prof_loc['lon']),
                    (student_location['lat'], student_location['lon'])
                ).meters

                boundary_radius = float(session['boundary_radius'])
                if dist <= boundary_radius:
                    status = 'present'
                elif dist <= boundary_radius * 2:
                    status = 'manual_review'
                else:
                    status = 'absent'

                attendance = record_attendance(
                    session_id=session_id,
                    student_id=response.user.id,
                    student_location=student_location,
                    distance=dist,
                    status=status
                )

                self.wfile.write(json.dumps({
                    'student_id': response.user.id,
                    'session_id': session_id,
                    'distance': dist,
                    'timestamp': attendance['timestamp'],
                    'status': status
                }).encode())

            except Exception as e:
                self.wfile.write(json.dumps({'error': str(e)}).encode())

    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()

        if self.path == '/':
            with open('login.html', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/professor.html':
            with open('professor.html', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/student.html':
            with open('student.html', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/professor.css':
            with open('professor.css', 'rb') as file:
                self.wfile.write(file.read())
        elif self.path == '/student.css':
            with open('student.css', 'rb') as file:
                self.wfile.write(file.read()) 