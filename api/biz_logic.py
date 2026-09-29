import datetime

def calculate_bill(order_items, discount_percent=0.0, service_charge_percent=10.0, vat_percent=7.0):
    """คำนวณ ยอดรวม ส่วนลด ค่าบริการ และภาษี"""
    try:
        subtotal = 0.0
        for item in order_items:
            price = float(item.get('price', 0))
            qty = int(item.get('quantity', 1))
            if price < 0 or qty <= 0:
                return {"status": "error", "message": "ราคาหรือจำนวนสินค้าต้องไม่ติดลบ"}
            subtotal += price * qty

        if discount_percent > 100 or discount_percent < 0:
            discount_percent = 0.0

        discount_amt = subtotal * (discount_percent / 100.0)
        after_discount = subtotal - discount_amt
        
        service_charge = after_discount * (service_charge_percent / 100.0)
        taxable_amt = after_discount + service_charge
        vat = taxable_amt * (vat_percent / 100.0)
        total_net = taxable_amt + vat

        return {
            "status": "success",
            "subtotal": round(subtotal, 2),
            "discount": round(discount_amt, 2),
            "service_charge": round(service_charge, 2),
            "vat": round(vat, 2),
            "total_net": round(total_net, 2)
        }
    except Exception:
        return {"status": "error", "message": "รูปแบบข้อมูลการคำนวณไม่ถูกต้อง"}

def validate_menu_item(data):
    """ตรวจสอบความถูกต้องของการกรอกข้อมูลเมนูอาหาร"""
    try:
        name = str(data.get('name', '')).strip()
        price = float(data.get('price', -1))
        category = str(data.get('category', '')).strip()

        if not name or len(name) < 2:
            return {"valid": False, "message": "ชื่อเมนูต้องมีความยาวอย่างน้อย 2 ตัวอักษร"}
        if price <= 0:
            return {"valid": False, "message": "ราคาเมนูต้องมากกว่า 0 บาท"}
        if not category:
            return {"valid": False, "message": "กรุณาระบุหมวดหมู่เมนู"}

        return {"valid": True, "data": {"name": name, "price": price, "category": category}}
    except ValueError:
        return {"valid": False, "message": "ราคาต้องเป็นตัวเลขเท่านั้น"}
    except Exception:
        return {"valid": False, "message": "ข้อมูลเมนูไม่ถูกต้อง"}

def calculate_member_points(total_net, rate=100):
    """คำนวณแต้มสะสมสมาชิก (100 บาท = 1 แต้ม)"""
    try:
        if total_net <= 0:
            return 0
        return int(total_net // rate)
    except Exception:
        return 0

def create_audit_log(username, action, details=""):
    """สร้างตารางเก็บบันทึกประวัติการกระทำสำคัญ"""
    try:
        now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return {
            "timestamp": now,
            "user": username if username else "Unknown",
            "action": action,
            "details": details
        }
    except Exception:
        return {"timestamp": "", "user": "System", "action": action, "details": details}

def filter_out_of_stock_items(menu_list):
    """กรองรายการอาหารเพื่อไม่ให้ลูกค้าสั่งเมนูที่หมดได้"""
    try:
        available_items = []
        for item_id, item in menu_list.items():
            if not item.get('is_out_of_stock', False):
                available_items.append({"id": item_id, **item})
        return available_items
    except Exception:
        return []

def process_table_transfer(old_table_id, new_table_id, tables_dict):
    """การย้ายโต๊ะอาหาร"""
    try:
        if old_table_id not in tables_dict or new_table_id not in tables_dict:
            return {"success": False, "message": "ไม่พบโต๊ะที่ระบุ"}
        if tables_dict[new_table_id].get("status") != "available":
            return {"success": False, "message": "โต๊ะปลายทางไม่ว่าง"}
        
        order_id = tables_dict[old_table_id].get("current_order_id")
        return {
            "success": True,
            "old_table_updates": {"status": "available", "current_order_id": ""},
            "new_table_updates": {"status": "occupied", "current_order_id": order_id}
        }
    except Exception:
        return {"success": False, "message": "เกิดข้อผิดพลาดในการย้ายโต๊ะ"}