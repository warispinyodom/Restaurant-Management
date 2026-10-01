import json
import urllib.request
import urllib.error
import ssl
from werkzeug.security import check_password_hash

# URL ฐานข้อมูล Firebase Realtime Database
FIREBASE_URL = "https://webapplication-e7922-default-rtdb.asia-southeast1.firebasedatabase.app"

# สร้าง SSL Context รองรับการเชื่อมต่อ REST API ป้องกัน SSL Certificate Error
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

def get_all_users():
    """ดึงข้อมูลผู้ใช้ทั้งหมดจาก Firebase REST API"""
    url = f"{FIREBASE_URL}/users.json"
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0'}, 
            method='GET'
        )
        with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
            if response.status == 200:
                data = response.read().decode('utf-8')
                parsed_data = json.loads(data)
                return parsed_data if isinstance(parsed_data, dict) else {}
    except Exception as e:
        print(f"System Error (get_all_users): {e}")
        return {}
    return {}

def create_user(username, password, role):
    """บันทึกข้อมูลผู้ใช้ใหม่ลง Firebase"""
    url = f"{FIREBASE_URL}/users.json"
    payload = {
        "username": username,
        "password": password,
        "role": role,
        "is_active": True
    }
    data = json.dumps(payload).encode('utf-8')
    try:
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={
                'Content-Type': 'application/json',
                'User-Agent': 'Mozilla/5.0'
            }, 
            method='POST'
        )
        with urllib.request.urlopen(req, context=ssl_context, timeout=10) as response:
            if response.status in [200, 201]:
                return True
    except Exception as e:
        print(f"System Error (create_user): {e}")
        return False
    return False

def validate_registration(username, password, role):
    if not isinstance(username, str) or not isinstance(password, str):
        return False, "ข้อมูลต้องเป็นตัวอักษร"
    if len(username) < 3 or len(password) < 4:
        return False, "ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร และรหัสผ่าน 4 ตัวอักษร"
    if not validate_role(role):
        return False, "สิทธิ์ผู้ใช้งานไม่ถูกต้องตามระบบ"
    return True, "ข้อมูลถูกต้อง"

def validate_role(role):
    valid_roles = ["admin", "staff", "customer"]
    return role in valid_roles

def check_credentials(username, password):
    users = get_all_users()
    if not isinstance(users, dict):
        return False, None

    for uid, info in users.items():
        if isinstance(info, dict) and info.get('username') == username:
            stored_password = info.get('password')
            if not stored_password:
                continue
            
            # รองรับทั้งรหัสผ่านที่ Hashed (scrypt/pbkdf2) และแบบ Plain-text
            is_match = False
            try:
                is_match = check_password_hash(stored_password, password)
            except Exception:
                is_match = (stored_password == password)

            if is_match:
                return True, info
    return False, None