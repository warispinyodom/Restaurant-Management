import json
import ssl
import urllib.request
import urllib.error

FIREBASE_URL = "https://webapplication-e7922-default-rtdb.asia-southeast1.firebasedatabase.app"

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

                def process_order(order_id, order_info):
                    if isinstance(order_info, dict):
                        item = dict(order_info)
                        item['id'] = str(order_id)
                        
                        # จัดการเลขโต๊ะ (ดึงคีย์ที่เป็นไปได้ทั้งหมด + ป้องกันค่าว่าง/เครื่องหมาย -)
                        table_val = (
                            item.get('table_no') or 
                            item.get('table') or 
                            item.get('table_number') or 
                            item.get('tableNo')
                        )
                        if not table_val or str(table_val).strip() in ['-', '', 'None', 'null']:
                            item['table_no'] = 'ไม่ระบุ'
                        else:
                            item['table_no'] = str(table_val).strip()
                        
                        raw_items = item.get('items', [])
                        if isinstance(raw_items, dict):
                            items_list = list(raw_items.values())
                        elif isinstance(raw_items, list):
                            items_list = raw_items
                        else:
                            items_list = []
                            
                        item['items'] = items_list
                        item['order_items'] = items_list
                        return item
                    return None

                if isinstance(data, dict):
                    for order_id, order_info in data.items():
                        processed = process_order(order_id, order_info)
                        if processed:
                            orders.append(processed)
                elif isinstance(data, list):
                    for idx, order_info in enumerate(data):
                        processed = process_order(idx, order_info)
                        if processed:
                            orders.append(processed)

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

# ==================== 2. จัดการเมนูและหมวดหมู่ (Menus & Categories) ====================

def get_all_categories():
    """ดึงข้อมูลหมวดหมู่ทั้งหมดจาก Firebase"""
    url = f"{FIREBASE_URL}/categories.json"
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, context=ssl_context) as response:
            if response.status == 200:
                raw_data = response.read().decode('utf-8')
                data = json.loads(raw_data) if raw_data else {}
                return data if isinstance(data, dict) else {}
    except Exception as e:
        print(f"System Error (get_all_categories): {e}")
    return {}

def get_all_menus():
    """ดึงรายการเมนูทั้งหมดจาก Firebase (GET /menus.json)"""
    categories = get_all_categories()
    url = f"{FIREBASE_URL}/menus.json"
    try:
        req = urllib.request.Request(url, method='GET')
        with urllib.request.urlopen(req, context=ssl_context) as response:
            if response.status == 200:
                data = json.loads(response.read().decode('utf-8'))
                if not data:
                    return []
                
                menus = []
                
                def process_item(menu_id, menu_info):
                    if isinstance(menu_info, dict):
                        item = dict(menu_info)
                        item['id'] = str(menu_id)
                        
                        cat_id = item.get('category_id', '')
                        cat_name_from_db = categories.get(cat_id, {}).get('name') if isinstance(categories, dict) and cat_id in categories else None
                        item['category'] = cat_name_from_db or item.get('category', 'ทั่วไป')
                        
                        # ป้องกัน UndefinedError สำหรับ stock, price, discount
                        if 'stock' not in item:
                            item['stock'] = None
                        if 'price' not in item:
                            item['price'] = 0
                        if 'discount' not in item:
                            item['discount'] = 0
                        
                        if 'status' not in item:
                            is_avail = item.get('is_available', True)
                            item['status'] = 'available' if is_avail else 'out_of_stock'
                            
                        return item
                    return None

                if isinstance(data, dict):
                    for menu_id, menu_info in data.items():
                        processed = process_item(menu_id, menu_info)
                        if processed:
                            menus.append(processed)
                            
                elif isinstance(data, list):
                    for idx, menu_info in enumerate(data):
                        processed = process_item(idx, menu_info)
                        if processed:
                            menus.append(processed)

                return menus
    except Exception as e:
        print(f"System Error (get_all_menus): {e}")
        return []
    return []

def update_menu_item_db(menu_id, update_data):
    """อัปเดตราคา สต็อก และสถานะอาหารใน Firebase (PATCH /menus/{menu_id}.json)"""
    url = f"{FIREBASE_URL}/menus/{menu_id}.json"
    
    payload = {}
    if 'price' in update_data:
        payload['price'] = update_data['price']
    if 'discount' in update_data:
        payload['discount'] = update_data['discount']
    if 'stock' in update_data:
        payload['stock'] = update_data['stock']
    if 'status' in update_data:
        payload['status'] = update_data['status']
        payload['is_available'] = (update_data['status'] == 'available')
    elif 'is_available' in update_data:
        payload['is_available'] = update_data['is_available']

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
        print(f"System Error (update_menu_item_db): {e}")
        return False

def bulk_update_menu_items_db(items_data):
    """
    อัปเดตข้อมูลแบบกลุ่มหลายรายการพร้อมกันใน Firebase
    items_data: dict ในรูปแบบ { "menu_id_1": { "price": 50, ... }, "menu_id_2": { ... } }
    """
    if not items_data or not isinstance(items_data, dict):
        return False

    url = f"{FIREBASE_URL}/menus.json"
    payload = {}

    for menu_id, update_data in items_data.items():
        if 'price' in update_data:
            payload[f"{menu_id}/price"] = update_data['price']
        if 'discount' in update_data:
            payload[f"{menu_id}/discount"] = update_data['discount']
        if 'stock' in update_data:
            payload[f"{menu_id}/stock"] = update_data['stock']
        if 'status' in update_data:
            payload[f"{menu_id}/status"] = update_data['status']
            payload[f"{menu_id}/is_available"] = (update_data['status'] == 'available')

    if not payload:
        return True

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
        print(f"System Error (bulk_update_menu_items_db): {e}")
        return False