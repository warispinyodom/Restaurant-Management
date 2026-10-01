import json
import urllib.request
import urllib.error
from werkzeug.security import check_password_hash

# URL ฐานข้อมูล Firebase Realtime Database
FIREBASE_URL = "https://webapplication-e7922-default-rtdb.asia-southeast1.firebasedatabase.app"

# 1. ดึงข้อมูลผู้ใช้ทั้งหมด
def get_all_users():
    """ดึงข้อมูลผู้ใช้จาก Firebase REST API"""
    url = f"{FIREBASE_URL}/users.json"
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = response.read().decode('utf-8')
                parsed_data = json.loads(data)
                return parsed_data if parsed_data else {}
    except Exception as e:
        print(f"System Error (get_all_users): {e}")
        return {}
    return {}

# 2. เพิ่มผู้ใช้ใหม่
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
            headers={'Content-Type': 'application/json'}, 
            method='POST'
        )
        with urllib.request.urlopen(req) as response:
            if response.status in [200, 201]:
                return True
    except Exception as e:
        print(f"System Error (create_user): {e}")
        return False
    return False

# 3. ตรวจสอบความถูกต้องของข้อมูลสมัครสมาชิก
def validate_registration(username, password, role):
    if not isinstance(username, str) or not isinstance(password, str):
        return False, "ข้อมูลต้องเป็นตัวอักษร"
    if len(username) < 3 or len(password) < 4:
        return False, "ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร และรหัสผ่าน 4 ตัวอักษร"
    if not validate_role(role):
        return False, "สิทธิ์ผู้ใช้งานไม่ถูกต้องตามระบบ"
    return True, "ข้อมูลถูกต้อง"

# 4. ตรวจสอบสิทธิ์การใช้งาน
def validate_role(role):
    valid_roles = ["admin", "staff", "customer"]
    return role in valid_roles

# 5. ตรวจสอบการ Login
def check_credentials(username, password):
    users = get_all_users()
    for uid, info in users.items():
        if isinstance(info, dict):
            stored_password = info.get('password')
            
            # ตรวจสอบว่าเป็นรหัสผ่านที่ Hash ไว้หรือไม่ (เผื่อรหัสผ่านเก่าที่ยังไม่ Hash)
            if stored_password and stored_password.startswith('scrypt:'):
                is_match = check_password_hash(stored_password, password)
            else:
                is_match = (stored_password == password)

            if info.get('username') == username and is_match:
                return True, info
    return False, None