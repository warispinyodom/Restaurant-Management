from flask import Flask, request, session, redirect, url_for, render_template, flash, jsonify
import firebase_db
import core_logic
import os

app = Flask(__name__)
app.secret_key = "super_secret_key_for_session" # เปลี่ยนเป็นคีย์ที่ปลอดภัยในการใช้งานจริง

# ==========================================
# 1. ระบบ Login & Session (Role-based)
# ==========================================
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        # ดึงข้อมูลผู้ใช้จาก Firebase
        users = firebase_db.get_data("users")
        for uid, u_data in users.items():
            if u_data.get('username') == username and u_data.get('password') == password:
                session['user_id'] = uid
                session['role'] = u_data.get('role') # 'admin', 'staff', 'customer'
                
                # บันทึก Log การเข้าสู่ระบบ
                log_data = core_logic.prepare_log_entry(uid, "LOGIN", "User logged in")
                firebase_db.post_data("logs", log_data)
                
                return redirect(url_for('dashboard'))
                
        flash("ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง", "error")
    return render_template('login.html')

# ==========================================
# เพิ่ม Route หน้าหลัก ( Redirect ไป Login หรือ Menu )
# ==========================================
@app.route('/')
def index():
    # ถ้าล็อกอินแล้ว ให้พาไปตามสิทธิ์ ถ้ายังไม่ล็อกอิน ให้ไปหน้า Login
    if 'role' in session:
        if session['role'] in ('admin', 'staff'):
            return redirect(url_for('dashboard'))
        return redirect(url_for('customer_menu'))
    return redirect(url_for('login'))

# ==========================================
# ดักจับ Favicon ป้องกัน Error
# ==========================================
@app.route('/favicon.ico')
@app.route('/favicon.png')
def favicon():
    return '', 204  # ส่งค่าว่าง (No Content) ป้องกัน Error 404/500

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

# ==========================================
# 2. Dashboard & Report
# ==========================================
@app.route('/dashboard')
def dashboard():
    # ตรวจสอบสิทธิ์ (Server-side validation)
    if not core_logic.check_permission(session.get('role'), ('admin', 'staff')):
        flash("คุณไม่มีสิทธิ์เข้าถึงหน้านี้", "error")
        return redirect(url_for('login'))
    
    # ดึงข้อมูลมาสรุป (ใช้ while/for ใน template หรือ python)
    orders = firebase_db.get_data("orders")
    total_sales = 0.0
    for o_id, o_data in orders.items():
        if o_data.get('status') == 'paid':
            total_sales += o_data.get('total', 0)
            
    return render_template('dashboard.html', total_sales=total_sales, role=session.get('role'))

# ==========================================
# 3. จัดการเมนู (CRUD + Validation + Pagination)
# ==========================================
@app.route('/menus', methods=['GET', 'POST'])
def manage_menus():
    if not core_logic.check_permission(session.get('role'), ('admin',)):
        return "Access Denied: เฉพาะ Admin เท่านั้น", 403

    # เพิ่มข้อมูลเมนู (Create)
    if request.method == 'POST':
        name = request.form.get('name')
        price = request.form.get('price')
        category = request.form.get('category')
        
        # ตรวจสอบข้อมูลฝั่งเซิร์ฟเวอร์ (ป้องกันกรอกตัวอักษรในช่องราคา หรือค่าติดลบ)
        is_valid, result = core_logic.validate_menu_input(name, price, category)
        if not is_valid:
            flash(result, "error") # result จะเป็นข้อความแจ้งเตือน
        else:
            result['is_out_of_stock'] = False
            # สร้างข้อมูลลง Firebase
            firebase_db.post_data("menus", result)
            
            # บันทึก Log
            log_data = core_logic.prepare_log_entry(session.get('user_id'), "CREATE_MENU", f"Added menu: {name}")
            firebase_db.post_data("logs", log_data)
            
            flash("เพิ่มเมนูสำเร็จ", "success")
            return redirect(url_for('manage_menus'))

    # อ่านข้อมูล (Read, Filter, Sort, Pagination)
    menus_raw = firebase_db.get_data("menus")
    search_kw = request.args.get('search', '')
    cat_filter = request.args.get('category', 'all')
    page = int(request.args.get('page', 1))
    
    filtered_menus = core_logic.filter_and_sort_menus(menus_raw, search_kw, cat_filter)
    paged_result = core_logic.paginate_list(filtered_menus, page, per_page=10)

    return render_template('menus.html', menus=paged_result)

# ==========================================
# 4. ระบบ Error Handling กลาง (ไม่แสดง Traceback )
# ==========================================
@app.errorhandler(500)
def internal_server_error(e):
    return render_template('error.html', message="เกิดข้อผิดพลาดที่เซิร์ฟเวอร์ กรุณาลองใหม่"), 500

@app.errorhandler(404)
def page_not_found(e):
    return render_template('error.html', message="ไม่พบหน้าที่คุณต้องการ"), 404

if __name__ == '__main__':
    # รันบน Local สำหรับทดสอบ
    app.run(debug=True)