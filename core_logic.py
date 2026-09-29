import math
from datetime import datetime

def check_permission(user_role, allowed_roles):
    if not user_role:
        return False
    return user_role in allowed_roles

def validate_registration(username, password, confirm_pass, name, existing_users):
    if not username or len(username) < 4:
        return False, "ชื่อผู้ใช้ต้องมีอย่างน้อย 4 ตัวอักษร"
    if not password or len(password) < 4:
        return False, "รหัสผ่านต้องมีอย่างน้อย 4 ตัวอักษร"
    if password != confirm_pass:
        return False, "รหัสผ่านและการยืนยันรหัสผ่านไม่ตรงกัน"
    if not name:
        return False, "กรุณากรอกชื่อ-นามสกุล"
        
    if isinstance(existing_users, dict):
        for user in existing_users.values():
            if isinstance(user, dict) and user.get('username') == username:
                return False, "ชื่อผู้ใช้นี้ถูกใช้งานแล้ว"
                
    return True, "สำเร็จ"

def validate_menu_input(name, price_str, category):
    if not name or not name.strip():
        return False, "กรุณากรอกชื่อเมนู"
    if not category or not category.strip():
        return False, "กรุณาระบุหมวดหมู่"
    try:
        price = float(price_str)
        if price <= 0:
            return False, "ราคาต้องมากกว่า 0 บาท"
    except (ValueError, TypeError):
        return False, "ราคาต้องเป็นตัวเลขที่ถูกต้อง"
        
    return True, {
        "name": name.strip(),
        "price": price,
        "category": category.strip()
    }

def filter_and_sort_menus(menus, search="", category="all", sort_by="name"):
    result = []
    if not isinstance(menus, dict):
        return result
        
    for mid, item in menus.items():
        if not isinstance(item, dict):
            continue
            
        item_copy = item.copy()
        item_copy['id'] = mid
        try:
            item_copy['price'] = float(item_copy.get('price', 0))
        except (ValueError, TypeError):
            item_copy['price'] = 0.0

        # Filter Search
        if search and search.lower() not in item_copy.get('name', '').lower():
            continue
            
        # Filter Category
        if category != "all" and item_copy.get('category') != category:
            continue
            
        result.append(item_copy)
        
    # Sorting
    if sort_by == "price_asc":
        result.sort(key=lambda x: x['price'])
    elif sort_by == "price_desc":
        result.sort(key=lambda x: x['price'], reverse=True)
    else:
        result.sort(key=lambda x: x.get('name', ''))
        
    return result

def paginate_list(items, page=1, per_page=6):
    total_items = len(items)
    total_pages = math.ceil(total_items / per_page) if total_items > 0 else 1
    
    if page < 1: page = 1
    if page > total_pages: page = total_pages
    
    start_idx = (page - 1) * per_page
    end_idx = start_idx + per_page
    
    return {
        "items": items[start_idx:end_idx],
        "current_page": page,
        "total_pages": total_pages,
        "total_items": total_items
    }

def extract_categories(menus):
    cats = set()
    if isinstance(menus, dict):
        for item in menus.values():
            if isinstance(item, dict) and item.get('category'):
                cats.add(item.get('category'))
    return list(cats)

def prepare_log_entry(user_id, role, action, detail):
    return {
        "user_id": user_id,
        "role": role,
        "action": action,
        "detail": detail,
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    }