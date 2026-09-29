from http.server import BaseHTTPRequestHandler
import json
import urllib.request
import hashlib

# เปลี่ยนเป็น URL Firebase ของคุณ
FIREBASE_URL = "https://restaurant-management-a0b00-default-rtdb.asia-southeast1.firebasedatabase.app"

def hash_password(password):
    """เข้ารหัสผ่านด้วย SHA-256"""
    return hashlib.sha256(password.encode()).hexdigest()

class handler(BaseHTTPRequestHandler):
    def send_response_data(self, data, status_code=200):
        self.send_response(status_code)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def do_POST(self):
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length).decode('utf-8')
        
        try:
            req_data = json.loads(body)
        except:
            req_data = {}

        # ----------------------------------------------------
        # 1. ระบบเข้าสู่ระบบ (Login)
        # ----------------------------------------------------
        if self.path == '/api/login':
            username = req_data.get('username', '')
            password = req_data.get('password', '')

            try:
                # ดึงข้อมูลผู้ใช้จาก Firebase
                url = f"{FIREBASE_URL}/users/{username}.json"
                req = urllib.request.Request(url, method="GET")
                with urllib.request.urlopen(req) as response:
                    user_data = json.loads(response.read().decode('utf-8'))

                if user_data and user_data.get('password') == hash_password(password):
                    self.send_response_data({
                        "status": "success", 
                        "role": user_data.get('role'),
                        "message": "เข้าสู่ระบบสำเร็จ"
                    })
                else:
                    self.send_response_data({"status": "error", "message": "Username หรือ Password ไม่ถูกต้อง"}, 401)
            except Exception as e:
                self.send_response_data({"status": "error", "message": "ไม่สามารถเชื่อมต่อฐานข้อมูลได้"}, 500)

        # ----------------------------------------------------
        # 2. ระบบสมัครสมาชิก (Register)
        # ----------------------------------------------------
        elif self.path == '/api/register':
            username = req_data.get('username', '')
            password = req_data.get('password', '')
            role = req_data.get('role', 'guest') # ค่าเริ่มต้นคือ guest

            if not username or not password:
                self.send_response_data({"status": "error", "message": "กรุณากรอกข้อมูลให้ครบถ้วน"}, 400)
                return

            try:
                # เช็คว่ามีผู้ใช้นี้อยู่แล้วหรือไม่
                check_url = f"{FIREBASE_URL}/users/{username}.json"
                check_req = urllib.request.Request(check_url, method="GET")
                with urllib.request.urlopen(check_req) as check_resp:
                    existing_user = json.loads(check_resp.read().decode('utf-8'))
                    if existing_user is not None:
                        self.send_response_data({"status": "error", "message": "Username นี้มีผู้ใช้งานแล้ว"}, 400)
                        return

                # บันทึกผู้ใช้ใหม่ลง Firebase
                new_user_data = {
                    "password": hash_password(password),
                    "role": role
                }
                save_url = f"{FIREBASE_URL}/users/{username}.json"
                payload = json.dumps(new_user_data).encode('utf-8')
                save_req = urllib.request.Request(save_url, data=payload, method="PUT")
                save_req.add_header('Content-Type', 'application/json')
                
                with urllib.request.urlopen(save_req) as response:
                    self.send_response_data({"status": "success", "message": "สมัครสมาชิกสำเร็จ!"})
            except Exception as e:
                self.send_response_data({"status": "error", "message": "เกิดข้อผิดพลาดของเซิร์ฟเวอร์"}, 500)
        else:
            self.send_response_data({"status": "error", "message": "Endpoint not found"}, 404)