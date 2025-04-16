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

def handler(request):
    if request.method == 'OPTIONS':
        return {
            'statusCode': 200,
            'headers': {
                'Access-Control-Allow-Origin': '*',
                'Access-Control-Allow-Methods': 'GET, POST, OPTIONS',
                'Access-Control-Allow-Headers': 'Content-Type, Authorization'
            }
        }

    if request.method == 'POST':
        data = request.get_json()
        path = request.path

        if path == '/api/login':
            try:
                response = supabase.auth.sign_in_with_password({
                    "email": data.get('email'),
                    "password": data.get('password')
                })
                
                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
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
                }
            except Exception as e:
                return {
                    'statusCode': 400,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': str(e)})
                }

        elif path == '/api/generate_session':
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return {
                    'statusCode': 401,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Invalid token'})
                }

            token = auth_header.split(' ')[1]
            is_valid, response = verify_token(token)
            
            if not is_valid:
                return {
                    'statusCode': 401,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Invalid token'})
                }

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

                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'session_id': session['id'],
                        'qr_code_url': f'/api/get_qr/{session["id"]}',
                        'expiry': session['expiry']
                    })
                }

            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': str(e)})
                }

        elif path.startswith('/api/get_qr/'):
            session_id = path.split('/')[-1]
            try:
                qr = qrcode.QRCode(version=1, box_size=10, border=5)
                qr.add_data(session_id)
                qr.make(fit=True)
                qr_image = qr.make_image(fill_color="black", back_color="white")

                img_io = BytesIO()
                qr_image.save(img_io, 'PNG')
                img_io.seek(0)

                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'image/png',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': img_io.getvalue().decode('latin1')
                }

            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': str(e)})
                }

        elif path == '/api/verify_attendance':
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return {
                    'statusCode': 401,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Invalid token'})
                }

            token = auth_header.split(' ')[1]
            is_valid, response = verify_token(token)
            
            if not is_valid:
                return {
                    'statusCode': 401,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': 'Invalid token'})
                }

            try:
                session_id = data.get('session_data')
                student_location = data.get('student_location')

                session = get_session(session_id)
                if not session:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({'error': 'Invalid session'})
                    }

                expiry = datetime.fromisoformat(session['expiry'])
                if datetime.now(UTC) > expiry:
                    return {
                        'statusCode': 400,
                        'headers': {
                            'Content-Type': 'application/json',
                            'Access-Control-Allow-Origin': '*'
                        },
                        'body': json.dumps({'error': 'Session expired'})
                    }

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

                return {
                    'statusCode': 200,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({
                        'student_id': response.user.id,
                        'session_id': session_id,
                        'distance': dist,
                        'timestamp': attendance['timestamp'],
                        'status': status
                    })
                }

            except Exception as e:
                return {
                    'statusCode': 500,
                    'headers': {
                        'Content-Type': 'application/json',
                        'Access-Control-Allow-Origin': '*'
                    },
                    'body': json.dumps({'error': str(e)})
                }

    elif request.method == 'GET':
        path = request.path
        if path == '/':
            with open('login.html', 'rb') as file:
                content = file.read()
        elif path == '/professor.html':
            with open('professor.html', 'rb') as file:
                content = file.read()
        elif path == '/student.html':
            with open('student.html', 'rb') as file:
                content = file.read()
        elif path == '/professor.css':
            with open('professor.css', 'rb') as file:
                content = file.read()
        elif path == '/student.css':
            with open('student.css', 'rb') as file:
                content = file.read()
        else:
            return {
                'statusCode': 404,
                'headers': {
                    'Content-Type': 'text/plain',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': 'Not Found'
            }

        return {
            'statusCode': 200,
            'headers': {
                'Content-Type': 'text/html' if path.endswith('.html') else 'text/css',
                'Access-Control-Allow-Origin': '*'
            },
            'body': content.decode('utf-8')
        } 