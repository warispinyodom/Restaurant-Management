from datetime import datetime

# 1. ฟังก์ชันตรวจสอบสิทธิ์ (Role-based) - ใช้ if/else, in (tuple/list)
def check_permission(user_role: str, allowed_roles: tuple) -> bool:
    """ตรวจสอบว่าผู้ใช้มีสิทธิ์เข้าถึงหน้านี้หรือไม่"""
    if not user_role:
        return False
    return user_role in allowed_roles

# 2. ฟังก์ชันตรวจสอบข้อมูลนำเข้าเมนูอาหาร (Validation & Error Handling)
def validate_menu_input(name: str, price_str: str, category: str) -> tuple:
    """คืนค่า (สถานะความถูกต้อง, ข้อมูลที่แปลงแล้ว/ข้อความแจ้งเตือน)"""
    if not name.strip() or not category.strip():
        return False, "ชื่อเมนูและหมวดหมู่ห้ามว่าง"
    
    try:
        price = float(price_str)
        if price < 0:
            return False, "ราคาอาหารห้ามติดลบ"
        if price == 0:
            return False, "ราคาอาหารต้องมากกว่า 0"
    except ValueError:
        return False, "ราคาต้องเป็นตัวเลข (int หรือ float) เท่านั้น"
    
    return True, {"name": name, "price": price, "category": category}

# 3. ฟังก์ชันคำนวณบิล (ใช้ Loop for, ตัวแปรเลขทศนิยม)
def calculate_bill(order_items: list, discount_percent: float = 0.0, tax_rate: float = 0.07) -> dict:
    """คำนวณยอดรวม ส่วนลด ภาษี และยอดสุทธิ"""
    subtotal = 0.0
    for item in order_items:
        # สมมติ item เป็น dict = {"price": 50, "qty": 2}
        subtotal += (item.get("price", 0) * item.get("qty", 0))
    
    discount_amount = subtotal * (discount_percent / 100)
    after_discount = subtotal - discount_amount
    tax_amount = after_discount * tax_rate
    grand_total = after_discount + tax_amount
    
    return {
        "subtotal": round(subtotal, 2),
        "discount": round(discount_amount, 2),
        "tax": round(tax_amount, 2),
        "grand_total": round(grand_total, 2)
    }

# 4. ฟังก์ชันกรอง ค้นหา และเรียงลำดับ (Search, Filter, Sort)
def filter_and_sort_menus(menus: dict, search_kw: str = "", category: str = "all", sort_by: str = "name") -> list:
    """ใช้ Set / List / Dict ในการจัดการข้อมูล"""
    result = []
    for m_id, m_data in menus.items():
        m_data['id'] = m_id
        
        # ค้นหาและกรอง (and / or)
        match_search = (search_kw.lower() in m_data['name'].lower()) if search_kw else True
        match_category = (m_data['category'] == category) if category != "all" else True
        
        if match_search and match_category:
            result.append(m_data)
            
    # เรียงลำดับ
    if sort_by == "price_asc":
        result.sort(key=lambda x: x['price'])
    elif sort_by == "price_desc":
        result.sort(key=lambda x: x['price'], reverse=True)
    else:
        result.sort(key=lambda x: x['name'])
        
    return result

# 5. ฟังก์ชันแบ่งหน้า (Pagination)
def paginate_list(data_list: list, page: int, per_page: int) -> dict:
    """แบ่งหน้าข้อมูล"""
    total_items = len(data_list)
    total_pages = (total_items + per_page - 1) // per_page
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    return {
        "items": data_list[start_idx:end_idx],
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_items
    }

# 6. ฟังก์ชันบันทึก Log (Audit Log)
def prepare_log_entry(user_id: str, action: str, details: str) -> dict:
    """เตรียมข้อมูลสำหรับการบันทึก Log ลงฐานข้อมูล"""
    return {
        "timestamp": datetime.now().isoformat(),
        "user_id": user_id,
        "action": action,
        "details": details
    }