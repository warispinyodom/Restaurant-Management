import json
import ssl
import urllib.request
import urllib.error

FIREBASE_URL = "https://webapplication-e7922-default-rtdb.asia-southeast1.firebasedatabase.app"

# SSL Context สำหรับข้ามการตรวจใบรับรองความปลอดภัย ป้องกันปัญหา SSL error ใน Localhost
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# ==================== 1. จัดการออเดอร์ (Orders) ====================

def get_all_orders():
    """ดึงข้อมูลออเดอร์ทั้งหมดจาก Firebase (GET /orders.json)"""
    url = f"{FIREBASE_URL}/orders.json"
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, context=ssl_context) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if not data:
                    return []
                
                orders = []
                # กรณี Firebase ส่งกลับมาเป็น Dictionary
                if isinstance(data, dict):
                    for order_id, order_info in data.items():
                        if isinstance(order_info, dict):
                            order_info['id'] = str(order_id)
                            orders.append(order_info)
                # กรณี Firebase ส่งกลับมาเป็น List
                elif isinstance(data, list):
                    for idx, order_info in enumerate(data):
                        if isinstance(order_info, dict):
                            order_info['id'] = str(idx)
                            orders.append(order_info)

                return orders
    except Exception as e:
        print(f"System Error (get_all_orders): {e}")
        return []
    return []

def update_order_status_db(order_id, status):
    """อัปเดตสถานะออเดอร์ใน Firebase (PATCH /orders/{order_id}.json)"""
    url = f"{FIREBASE_URL}/orders/{order_id}.json"
    payload = {"status": status}
    data = json.dumps(payload).encode('utf-8')
    try:
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={'Content-Type': 'application/json'}, 
            method='PATCH'
        )
        with urllib.request.urlopen(req, context=ssl_context) as response:
            return response.status in [200, 201]
    except Exception as e:
        print(f"System Error (update_order_status_db): {e}")
        return False

# ==================== 2. จัดการเมนูและสต็อก (Menus) ====================

def get_all_menus():
    """ดึงรายการเมนูทั้งหมดจาก Firebase (GET /menus.json)"""
    url = f"{FIREBASE_URL}/menus.json"
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, context=ssl_context) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if not data:
                    return []
                
                menus = []
                # กรณี Firebase ส่งกลับมาเป็น Dictionary
                if isinstance(data, dict):
                    for menu_id, menu_info in data.items():
                        if isinstance(menu_info, dict):
                            menu_info['id'] = str(menu_id)
                            menus.append(menu_info)
                # กรณี Firebase ส่งกลับมาเป็น List
                elif isinstance(data, list):
                    for idx, menu_info in enumerate(data):
                        if isinstance(menu_info, dict):
                            menu_info['id'] = str(idx)
                            menus.append(menu_info)

                return menus
    except Exception as e:
        print(f"System Error (get_all_menus): {e}")
        return []
    return []

def update_menu_item_db(menu_id, update_data):
    """อัปเดตราคา สต็อก หรือสถานะอาหาร (PATCH /menus/{menu_id}.json)"""
    url = f"{FIREBASE_URL}/menus/{menu_id}.json"
    data = json.dumps(update_data).encode('utf-8')
    try:
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={'Content-Type': 'application/json'}, 
            method='PATCH'
        )
        with urllib.request.urlopen(req, context=ssl_context) as response:
            return response.status in [200, 201]
    except Exception as e:
        print(f"System Error (update_menu_item_db): {e}")
        return False