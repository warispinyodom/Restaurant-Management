import urllib.request
import json
from .file_manager import load_local_data

# URL Realtime Database จากโปรเจกต์ของคุณ
FIREBASE_URL = "https://webapplication-e7922-default-rtdb.asia-southeast1.firebasedatabase.app/"

def get_data(path):
    """ดึงข้อมูลจาก Firebase หากเกิดข้อผิดพลาดจะดึงจาก Local File แทน"""
    try:
        url = f"{FIREBASE_URL}/{path}.json"
        req = urllib.request.Request(url, method="GET")
        with urllib.request.urlopen(req, timeout=3) as response:
            data = response.read().decode('utf-8')
            parsed = json.loads(data) if data != "null" else None
            if parsed is not None:
                return parsed
    except Exception:
        pass
    
    # Fallback มาใช้ Local File หากเชื่อมต่อไม่ได้
    local_data = load_local_data()
    return local_data.get(path, {})

def update_data(path, data_dict):
    """อัปเดตข้อมูลขึ้น Firebase (PATCH)"""
    try:
        url = f"{FIREBASE_URL}/{path}.json"
        payload = json.dumps(data_dict).encode('utf-8')
        req = urllib.request.Request(url, data=payload, method="PATCH")
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=3) as response:
            return {"status": "success", "code": response.getcode()}
    except Exception as e:
        return {"error": "ไม่สามารถอัปเดต Firebase ได้", "details": str(e)}

def seed_firebase_from_local():
    """ซิงค์ข้อมูลตั้งต้นจาก data.json ไปยัง Firebase"""
    try:
        local_data = load_local_data()
        if not local_data:
            return {"status": "error", "message": "ไม่พบข้อมูลใน data.json"}
            
        url = f"{FIREBASE_URL}/.json"
        payload = json.dumps(local_data).encode('utf-8')
        req = urllib.request.Request(url, data=payload, method="PATCH")
        req.add_header('Content-Type', 'application/json')
        with urllib.request.urlopen(req, timeout=5) as response:
            return {"status": "success", "message": "ซิงค์ข้อมูลลง Firebase เรียบร้อยแล้ว"}
    except Exception as e:
        return {"status": "error", "message": f"ซิงค์ข้อมูลไม่สำเร็จ: {str(e)}"}