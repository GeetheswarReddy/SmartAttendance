from dotenv import load_dotenv
load_dotenv()
import os
from supabase import create_client
from datetime import datetime, timedelta, UTC
import geocoder

# Initialize Supabase client
url = os.environ.get("SUPABASE_URL")
key = os.environ.get("SUPABASE_KEY")
supabase = create_client(url, key)

def get_current_location():
    """Get current location using geocoder"""
    try:
        g = geocoder.ip('me')
        if g.latlng:
            return {'lat': g.latlng[0], 'lon': g.latlng[1]}
    except Exception as e:
        print(f"Error getting location: {e}")
    return None

def create_session(user_id, prof_location, boundary_radius, token):
    """Create a new attendance session"""
    expiry = datetime.now(UTC) + timedelta(minutes=10)
    data = {
        'prof_id': user_id,
        'prof_location': prof_location,
        'boundary_radius': boundary_radius,
        'token': token,
        'expiry': expiry.isoformat()
    }
    result = supabase.table('sessions').insert(data).execute()
    return result.data[0]

def get_session(session_id):
    """Get session by ID"""
    result = supabase.table('sessions').select('*').eq('id', session_id).execute()
    if result.data:
        return result.data[0]
    return None

def get_user_sessions(user_id):
    """Get all sessions for a professor"""
    result = supabase.table('sessions').select('*').eq('prof_id', user_id).execute()
    return result.data

def record_attendance(session_id, student_id, student_location, distance, status):
    """Record student attendance"""
    data = {
        'session_id': session_id,
        'student_id': student_id,
        'student_location': student_location,
        'distance': distance,
        'status': status
    }
    result = supabase.table('attendance').insert(data).execute()
    return result.data[0]

def get_attendance_by_session(session_id):
    """Get all attendance records for a session"""
    result = supabase.table('attendance').select('*').eq('session_id', session_id).execute()
    return result.data

def get_attendance_by_student(student_id):
    """Get all attendance records for a student"""
    result = supabase.table('attendance').select('*').eq('student_id', student_id).execute()
    return result.data

def get_user_role(user_id):
    """Get user role from auth.users table"""
    result = supabase.table('users').select('role').eq('auth_id', user_id).execute()
    if result.data:
        return result.data[0]['role']
    return None

data=supabase.table('users').select('*').execute()
print(data)