import json
import urllib.request
import urllib.error

FIREBASE_URL = "https://webapplication-e7922-default-rtdb.asia-southeast1.firebasedatabase.app"

# ==================== 1. จัดการออเดอร์ (Orders) ====================

def get_all_orders():
    """ดึงข้อมูลออเดอร์ทั้งหมดจาก Firebase (GET /orders.json)"""
    url = f"{FIREBASE_URL}/orders.json"
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if not data:
                    return []
                orders = []
                for order_id, order_info in data.items():
                    if isinstance(order_info, dict):
                        order_info['id'] = order_id
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
        with urllib.request.urlopen(req) as response:
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
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if not data:
                    return []
                menus = []
                for menu_id, menu_info in data.items():
                    if isinstance(menu_info, dict):
                        menu_info['id'] = menu_id
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
        with urllib.request.urlopen(req) as response:
            return response.status in [200, 201]
    except Exception as e:
        print(f"System Error (update_menu_item_db): {e}")
        return False