import datetime
from http.server import BaseHTTPRequestHandler
import json

from .firebase_db import get_data, update_data, seed_firebase_from_local
from .auth import authenticate_user, check_permission
from .biz_logic import calculate_bill, validate_menu_item, create_audit_log, process_table_transfer
from .file_manager import save_local_data, load_local_data

class handler(BaseHTTPRequestHandler):

    def _send_json(self, data, status_code=200):
        try:
            self.send_response(status_code)
            self.send_header('Content-type', 'application/json')
            self.send_header('Access-Control-Allow-Origin', '*')
            self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
            self.send_header('Access-Control-Allow-Headers', 'Content-Type, Authorization-Role')
            self.end_headers()
            self.wfile.write(json.dumps(data, ensure_ascii=False).encode('utf-8'))
        except Exception:
            pass

    def do_OPTIONS(self):
        self._send_json({"status": "ok"}, 200)

    def do_GET(self):
        try:
            path = self.path.split('?')[0]
            
            if path == '/api/menus':
                self._send_json(get_data("menus"))
            elif path == '/api/tables':
                self._send_json(get_data("tables"))
            elif path == '/api/kitchen':
                self._send_json(get_data("kitchen"))
            elif path == '/api/logs':
                user_role = self.headers.get('Authorization-Role', 'customer')
                if not check_permission(user_role, 'admin'):
                    self._send_json({"error": "ไม่มีสิทธิ์เข้าถึงข้อมูล"}, 403)
                    return
                self._send_json(get_data("audit_logs"))
            else:
                self._send_json({"error": "Endpoint not found"}, 404)
        except Exception:
            self._send_json({"error": "เกิดข้อผิดพลาดภายในเซิร์ฟเวอร์"}, 500)

    def do_POST(self):
        try:
            content_length = int(self.headers.get('Content-Length', 0))
            body = self.rfile.read(content_length).decode('utf-8') if content_length > 0 else "{}"
            data = json.loads(body)
            path = self.path

            # --- 1. เข้าสู่ระบบ ---
            if path == '/api/login':
                users = get_data("users")
                res = authenticate_user(data.get("username"), data.get("password"), users)
                self._send_json(res, 200 if res["success"] else 400)

            # --- 2. สั่งอาหารเข้าครัว ---
            elif path == '/api/order/create':
                table_id = data.get("table_id")
                items = data.get("items", [])
                
                if not table_id or not items:
                    self._send_json({"error": "ข้อมูลการสั่งอาหารไม่ครบถ้วน"}, 400)
                    return

                timestamp_id = int(datetime.datetime.now().timestamp())
                order_id = f"ord_{timestamp_id}"
                
                order_payload = {
                    "order_id": order_id,
                    "table_id": table_id,
                    "items": items,
                    "status": "pending",
                    "created_at": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }

                # อัปเดตลง Firebase และเปลี่ยนสถานะโต๊ะเป็น occupied
                update_data(f"kitchen/{order_id}", order_payload)
                update_data(f"tables/{table_id}", {"status": "occupied", "current_order_id": order_id})
                
                self._send_json({"status": "success", "message": "ส่งออเดอร์เข้าครัวเรียบร้อย", "order_id": order_id})

            # --- 3. อัปเดตสถานะอาหารในครัว ---
            elif path == '/api/kitchen/status':
                order_id = data.get("order_id")
                new_status = data.get("status") # pending -> cooking -> served
                
                if not order_id or not new_status:
                    self._send_json({"error": "ระบุข้อมูลไม่ครบ"}, 400)
                    return

                update_data(f"kitchen/{order_id}", {"status": new_status})
                self._send_json({"status": "success", "message": f"อัปเดตสถานะเป็น {new_status}"})

            # --- 4. ย้ายโต๊ะอาหาร ---
            elif path == '/api/table/transfer':
                tables = get_data("tables")
                res = process_table_transfer(data.get("old_table"), data.get("new_table"), tables)
                
                if res["success"]:
                    update_data(f"tables/{data.get('old_table')}", res["old_table_updates"])
                    update_data(f"tables/{data.get('new_table')}", res["new_table_updates"])
                    self._send_json({"status": "success", "message": "ย้ายโต๊ะเรียบร้อย"})
                else:
                    self._send_json({"error": res["message"]}, 400)

            # --- 5. เพิ่มเมนูอาหาร (Admin Only) ---
            elif path == '/api/menu/add':
                user_role = self.headers.get('Authorization-Role', '')
                if not check_permission(user_role, 'admin'):
                    self._send_json({"error": "ไม่มีสิทธิ์ดำเนินการ"}, 403)
                    return
                
                val = validate_menu_item(data)
                if not val["valid"]:
                    self._send_json({"error": val["message"]}, 400)
                    return

                menu_id = f"menu_{int(datetime.datetime.now().timestamp())}"
                new_item = {
                    "name": val["data"]["name"],
                    "price": val["data"]["price"],
                    "category": val["data"]["category"],
                    "is_out_of_stock": False
                }
                update_data(f"menus/{menu_id}", new_item)
                
                # บันทึก Audit Log
                log = create_audit_log(data.get("admin_user"), "เพิ่มเมนูอาหาร", f"เพิ่ม {val['data']['name']}")
                update_data(f"audit_logs/log_{int(datetime.datetime.now().timestamp())}", log)
                
                self._send_json({"status": "success", "message": "เพิ่มเมนูสำเร็จ"})

            # --- 6. คิดเงิน / เช็คบิล ---
            elif path == '/api/checkout':
                items = data.get("items", [])
                discount = float(data.get("discount", 0))
                bill = calculate_bill(items, discount)
                
                # หากชำระเงินสำเร็จ ให้เปลี่ยนสถานะโต๊ะเป็น available
                table_id = data.get("table_id")
                if table_id and bill.get("status") == "success":
                    update_data(f"tables/{table_id}", {"status": "available", "current_order_id": ""})

                self._send_json(bill)

            # --- 7. ซิงค์ข้อมูลลง Firebase ---
            elif path == '/api/seed':
                res = seed_firebase_from_local()
                self._send_json(res)

            else:
                self._send_json({"error": "Endpoint not found"}, 404)

        except json.JSONDecodeError:
            self._send_json({"error": "รูปแบบ JSON 不ถูกต้อง"}, 400)
        except Exception:
            self._send_json({"error": "เกิดข้อผิดพลาดในการประมวลผลคำขอ"}, 500)