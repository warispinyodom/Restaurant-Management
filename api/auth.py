import hashlib

def hash_password(password):
    """แปลงรหัสผ่านเป็น SHA-256 เพื่อความปลอดภัย"""
    try:
        if not password:
            return ""
        return hashlib.sha256(password.encode('utf-8')).hexdigest()
    except Exception:
        return ""

def authenticate_user(username, password, users_dict):
    """ตรวจสอบการเข้าสู่ระบบ"""
    try:
        if not username or not password or not isinstance(users_dict, dict):
            return {"success": False, "message": "กรุณากรอกข้อมูลให้ครบถ้วน"}
        
        hashed = hash_password(password)
        for user_id, user_info in users_dict.items():
            if user_info.get("username") == username:
                if user_info.get("password_hash") == hashed:
                    return {
                        "success": True,
                        "user": {
                            "id": user_id,
                            "username": user_info.get("username"),
                            "role": user_info.get("role", "customer"),
                            "points": user_info.get("member_points", 0)
                        }
                    }
                else:
                    return {"success": False, "message": "รหัสผ่านไม่ถูกต้อง"}
        return {"success": False, "message": "ไม่พบชื่อผู้ใช้งานนี้"}
    except Exception:
        return {"success": False, "message": "เกิดข้อผิดพลาดในการตรวจสอบสิทธิ์"}

def check_permission(user_role, required_role):
    """ตรวจสอบสิทธิ์การเข้าถึง API"""
    role_hierarchy = {"admin": 3, "staff": 2, "customer": 1}
    try:
        user_level = role_hierarchy.get(user_role.lower(), 0)
        req_level = role_hierarchy.get(required_role.lower(), 0)
        return user_level >= req_level
    except Exception:
        return False