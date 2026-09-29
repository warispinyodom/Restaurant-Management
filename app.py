from flask import Flask, request, session, redirect, url_for, render_template, flash, jsonify
import firebase_db
import core_logic

app = Flask(__name__)
app.secret_key = "restaurant_app_secret_key"

# ==========================================
# 0. ROOT & FAVICON ROUTES (แก้ไข Exception / และ favicon)
# ==========================================
@app.route('/')
def index():
    """หน้าแรก Redirect ไปตามสถานะการล็อกอิน"""
    if 'role' in session:
        if session['role'] in ('admin', 'staff'):
            return redirect(url_for('dashboard'))
        return redirect(url_for('customer_menu'))
    return redirect(url_for('login'))

@app.route('/favicon.ico')
@app.route('/favicon.png')
def favicon():
    """จัดการ favicon ไม่ให้เบราว์เซอร์พ่น Error 404/500"""
    return '', 204

# ==========================================
# 1. AUTHENTICATION (Login / Register / Logout)
# ==========================================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        confirm_pass = request.form.get('confirm_password', '')
        name = request.form.get('name', '')
        phone = request.form.get('phone', '')
        
        users = firebase_db.get_data("users")
        if not isinstance(users, dict):
            users = {}
            
        is_valid, msg = core_logic.validate_registration(username, password, confirm_pass, name, users)
        
        if not is_valid:
            flash(msg, "error")
        else:
            new_user = {
                "username": username,
                "password": password,
                "name": name,
                "phone": phone,
                "role": "customer",
                "points": 0
            }
            firebase_db.post_data("users", new_user)
            flash("สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ", "success")
            return redirect(url_for('login'))
            
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')
        
        users = firebase_db.get_data("users")
        if isinstance(users, dict):
            for uid, u_data in users.items():
                if isinstance(u_data, dict) and u_data.get('username') == username and u_data.get('password') == password:
                    session['user_id'] = uid
                    session['username'] = u_data.get('username')
                    session['name'] = u_data.get('name')
                    session['role'] = u_data.get('role')
                    
                    log = core_logic.prepare_log_entry(uid, session['role'], "LOGIN", f"User {username} logged in")
                    firebase_db.post_data("logs", log)
                    
                    if session['role'] in ('admin', 'staff'):
                        return redirect(url_for('dashboard'))
                    else:
                        return redirect(url_for('customer_menu'))
                        
        flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", "error")
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# 2. CUSTOMER ZONE (สำหรับลูกค้า)
# ==========================================
@app.route('/customer/menu')
def customer_menu():
    if not core_logic.check_permission(session.get('role'), ('customer', 'staff', 'admin')):
        return redirect(url_for('login'))
        
    menus = firebase_db.get_data("menus")
    if not isinstance(menus, dict):
        menus = {}
        
    search = request.args.get('search', '')
    category = request.args.get('category', 'all')
    sort_by = request.args.get('sort', 'name')
    
    try:
        page = int(request.args.get('page', 1))
    except ValueError:
        page = 1
    
    filtered = core_logic.filter_and_sort_menus(menus, search, category, sort_by)
    paginated = core_logic.paginate_list(filtered, page, per_page=6)
    categories = core_logic.extract_categories(menus)
    
    return render_template('customer_menu.html', data=paginated, categories=categories)

@app.route('/customer/order', methods=['POST'])
def customer_place_order():
    if not core_logic.check_permission(session.get('role'), ('customer', 'staff', 'admin')):
        return redirect(url_for('login'))
        
    table_num = request.form.get('table_number')
    menu_id = request.form.get('menu_id')
    qty_str = request.form.get('qty', '1')
    spicy_level = request.form.get('spicy', 'ปกติ')
    extra_egg = request.form.get('extra_egg') == 'yes'
    
    menus = firebase_db.get_data("menus")
    menu = menus.get(menu_id) if isinstance(menus, dict) else None
    
    if not menu or menu.get('is_out_of_stock'):
        flash("เมนูนี้หมดแล้ว ไม่สามารถสั่งได้", "error")
        return redirect(url_for('customer_menu'))
        
    try:
        qty = int(qty_str)
        if qty <= 0: raise ValueError
    except ValueError:
        flash("จำนวนต้องเป็นตัวเลขที่มากกว่า 0", "error")
        return redirect(url_for('customer_menu'))

    order_data = {
        "user_id": session.get('user_id'),
        "table_number": table_num,
        "menu_name": menu['name'],
        "price": menu['price'],
        "qty": qty,
        "options": f"เผ็ด: {spicy_level}" + (", เพิ่มไข่ดาว" if extra_egg else ""),
        "status": "pending",
        "timestamp": core_logic.datetime.now().strftime("%H:%M:%S")
    }
    firebase_db.post_data("orders", order_data)
    flash("สั่งอาหารเรียบร้อยแล้ว!", "success")
    return redirect(url_for('customer_menu'))

# ==========================================
# 3. STAFF & ADMIN ZONE (พนักงาน & แอดมิน)
# ==========================================
@app.route('/dashboard')
def dashboard():
    if not core_logic.check_permission(session.get('role'), ('admin', 'staff')):
        flash("คุณไม่มีสิทธิ์เข้าถึงหน้านี้", "error")
        return redirect(url_for('login'))
        
    orders = firebase_db.get_data("orders")
    total_sales = 0.0
    paid_count = 0
    
    if isinstance(orders, dict):
        for o in orders.values():
            if isinstance(o, dict) and o.get('status') == 'paid':
                total_sales += (o.get('price', 0) * o.get('qty', 1))
                paid_count += 1
            
    return render_template('dashboard.html', total_sales=total_sales, paid_count=paid_count, role=session.get('role'))

@app.route('/kitchen')
def kitchen_display():
    if not core_logic.check_permission(session.get('role'), ('admin', 'staff')):
        return redirect(url_for('login'))
        
    orders = firebase_db.get_data("orders")
    if not isinstance(orders, dict):
        orders = {}
    return render_template('kitchen.html', orders=orders)

@app.route('/order/update_status/<order_id>', methods=['POST'])
def update_order_status(order_id):
    if not core_logic.check_permission(session.get('role'), ('admin', 'staff')):
        return redirect(url_for('login'))
        
    new_status = request.form.get('status')
    firebase_db.patch_data(f"orders/{order_id}", {"status": new_status})
    return redirect(url_for('kitchen_display'))

# ==========================================
# 4. ADMIN ONLY ZONE (เฉพาะผู้จัดการ)
# ==========================================
@app.route('/admin/menus', methods=['GET', 'POST'])
def admin_manage_menus():
    if not core_logic.check_permission(session.get('role'), ('admin',)):
        flash("เฉพาะ Admin เท่านั้นที่เข้าถึงหน้านี้ได้", "error")
        return redirect(url_for('dashboard'))
        
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        category = request.form.get('category')
        
        is_valid, res = core_logic.validate_menu_input(name, price, category)
        if not is_valid:
            flash(res, "error")
        else:
            res['is_out_of_stock'] = False
            firebase_db.post_data("menus", res)
            
            log = core_logic.prepare_log_entry(session['user_id'], 'admin', 'CREATE_MENU', f"Added menu {name}")
            firebase_db.post_data("logs", log)
            flash("เพิ่มเมนูเรียบร้อย", "success")
            
    menus = firebase_db.get_data("menus")
    if not isinstance(menus, dict):
        menus = {}
    return render_template('admin_menus.html', menus=menus)

@app.route('/admin/menu/delete/<menu_id>', methods=['POST'])
def admin_delete_menu(menu_id):
    if not core_logic.check_permission(session.get('role'), ('admin',)):
        return redirect(url_for('dashboard'))
        
    firebase_db.delete_data(f"menus/{menu_id}")
    
    log = core_logic.prepare_log_entry(session['user_id'], 'admin', 'DELETE_MENU', f"Deleted menu {menu_id}")
    firebase_db.post_data("logs", log)
    
    flash("ลบเมนูเรียบร้อย", "success")
    return redirect(url_for('admin_manage_menus'))

# ==========================================
# 5. SAFE ERROR HANDLERS
# ==========================================
@app.errorhandler(404)
def not_found(e):
    try:
        return render_template('error.html', msg="ไม่พบหน้าที่คุณต้องการ (404)"), 404
    except Exception:
        return "<h1>404 Not Found</h1>", 404

@app.errorhandler(500)
def server_error(e):
    try:
        return render_template('error.html', msg="เกิดข้อผิดพลาดภายในระบบ (500)"), 500
    except Exception:
        return "<h1>500 Internal Server Error</h1>", 500

if __name__ == '__main__':
    app.run(debug=True)