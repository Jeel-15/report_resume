import os
import json
import uuid
os.environ['REGISTER_OTP_DEBUG'] = 'true'
os.environ['SQLITE_PATH'] = 'data/test_app.db'

from app import app
from models.user import User

client = app.test_client()

def test_auth_flow():
    results = {}
    
    # 1. GET /register
    try:
        resp = client.get('/register')
        results['GET_register'] = resp.status_code
    except Exception as e:
        results['GET_register_error'] = str(e)
        
    # 2. GET /login
    try:
        resp = client.get('/login')
        results['GET_login'] = resp.status_code
    except Exception as e:
        results['GET_login_error'] = str(e)
        
    # 3. POST /api/auth/register/send-otp
    email = f"test_{uuid.uuid4().hex[:8]}@example.com"
    password = "StrongPassword123!"
    name = "Test User"
    
    send_payload = {
        'email': email,
        'password': password,
        'name': name
    }
    
    resp_send = client.post('/api/auth/register/send-otp', json=send_payload)
    send_data = resp_send.get_json()
    results['POST_send_otp_status'] = resp_send.status_code
    results['POST_send_otp_json'] = send_data
    
    otp = send_data.get('otp') if send_data else None
    
    # 4. POST /api/auth/register/verify-otp
    if otp:
        verify_payload = {
            'email': email,
            'otp': otp
        }
        resp_verify = client.post('/api/auth/register/verify-otp', json=verify_payload)
        verify_data = resp_verify.get_json()
        results['POST_verify_otp_status'] = resp_verify.status_code
        results['POST_verify_otp_json'] = verify_data
    else:
        results['POST_verify_otp_skipped'] = "No OTP returned in send-otp response"
        
    # 5. Delete the test user
    try:
        user = User.objects(email=email).first()
        if user:
            user.delete()
            results['delete_user'] = "Success"
        else:
            results['delete_user'] = "User not found"
    except Exception as e:
        results['delete_user_error'] = str(e)

    return results

if __name__ == '__main__':
    res = test_auth_flow()
    print(json.dumps(res, indent=2))
