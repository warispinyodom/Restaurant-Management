import os
import sqlite3
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash
import urllib.request
import json

from models import get_db_connection, init_db
# 1. นำเข้าฟังก์ชันจาก auth_utils (Firebase Auth)
from auth_utils import (
    get_all_users, 
    create_user, 
    validate_registration, 
    check_credentials
)
# 2. นำเข้าฟังก์ชันสำหรับระบบ Staff (Firebase RTDB)
from staff_utils import (
    get_all_orders, 
    update_order_status_db, 
    get_all_menus, 
    update_menu_item_db
)

app = Flask(__name__)
app.secret_key = 'restaurant_super_secret'

# กำหนดโฟลเดอร์สำหรับเก็บไฟล์รูปภาพอัปโหลด
UPLOAD_FOLDER = os.path.join('static', 'uploads')
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

# สร้างโฟลเดอร์ uploads และสร้างตารางใน Database อัตโนมัติเมื่อเริ่มระบบ
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

# Helper ตรวจสอบสิทธิ์ Admin
def admin_required(func_route):
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("คุณไม่มีสิทธิ์เข้าถึงหน้านี้", "error")
            return redirect(url_for('home'))
        return func_route(*args, **kwargs)
    wrapper.__name__ = func_route.__name__
    return wrapper

# Helper ตรวจสอบสิทธิ์ Staff
def staff_required(func_route):
    def wrapper(*args, **kwargs):
        if session.get('role') not in ['staff', 'admin']:
            flash("คุณไม่มีสิทธิ์เข้าถึงหน้าพนักงาน", "error")
            return redirect(url_for('home'))
        return func_route(*args, **kwargs)
    wrapper.__name__ = func_route.__name__
    return wrapper

# ==========================================
# AUTHENTICATION ROUTES (ใช้ auth_utils)
# ==========================================

@app.route('/')
def home():
    if 'username' in session:
        role = session.get('role')
        if role == 'admin':
            return redirect(url_for('admin_dashboard'))
        elif role == 'staff':
            return redirect(url_for('staff_orders'))
        else:
            return redirect(url_for('customer_dashboard'))
    return redirect(url_for('signin'))

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        try:
            username = request.form['username'].strip()
            password = request.form['password'].strip()
            role = 'customer' 

            # ดึงผู้ใช้ทั้งหมดมาเช็คชื่อซ้ำจาก Firebase
            users = get_all_users()
            is_duplicate = any(
                info.get('username') == username 
                for uid, info in users.items() if isinstance(info, dict)
            )
            
            if is_duplicate:
                flash("ชื่อผู้ใช้นี้มีในระบบแล้ว", "error")
                return redirect(url_for('signup'))

            # Validate ข้อมูล
            is_valid, msg = validate_registration(username, password, role)
            if not is_valid:
                flash(msg, "error")
                return redirect(url_for('signup'))

            # --- เพิ่มบรรทัดนี้: เข้ารหัสผ่านก่อนบันทึก ---
            hashed_password = generate_password_hash(password)
            
            # บันทึกผู้ใช้ลง Firebase (ส่ง hashed_password ไปแทน password)
            if create_user(username, hashed_password, role):
                flash("สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ", "success")
                return redirect(url_for('signin'))
                
        except Exception:
            flash("เกิดข้อผิดพลาดของระบบ", "error")
            return redirect(url_for('signup'))

    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password'].strip()

        # ตรวจสอบการ Login กับ Firebase
        is_valid, user_info = check_credentials(username, password)
        
        if is_valid:
            session['username'] = user_info['username']
            session['role'] = user_info['role']
            
            role = user_info['role']
            if role == 'admin':
                return redirect(url_for('admin_dashboard'))
            elif role == 'staff':
                return redirect(url_for('staff_orders'))
            else:
                return redirect(url_for('customer_dashboard'))
        else:
            flash("ชื่อผู้ใช้งานหรือรหัสผ่านไม่ถูกต้อง", "error")

    return render_template('signin.html')

@app.route('/signout')
def signout():
    session.clear()
    return redirect(url_for('signin'))

# ==========================================
# DASHBOARD & STAFF ROUTES
# ==========================================

@app.route('/admin')
@admin_required
def admin_dashboard():
    return render_template('dashboard.html', username=session['username'], role=session['role'])

# --- ระบบ Staff (ออเดอร์ / สต็อก / สถานะพนักงาน) ---

@app.route('/staff/orders')
@staff_required
def staff_orders():
    staff_status = session.get('staff_status', 'ready')
    orders = get_all_orders()
    return render_template('staff/orders.html', orders=orders, staff_status=staff_status)

@app.route('/staff/status/update', methods=['POST'])
@staff_required
def update_staff_status():
    data = request.get_json()
    new_status = data.get('status')
    session['staff_status'] = new_status
    return jsonify({'status': 'success', 'message': f'เปลี่ยนสถานะพนักงานเป็น {new_status} สำเร็จ'})

@app.route('/staff/order/update-status/<order_id>', methods=['POST'])
@staff_required
def update_order_status(order_id):
    data = request.get_json()
    new_status = data.get('status')
    
    success = update_order_status_db(order_id, new_status)
    if success:
        return jsonify({'status': 'success', 'message': f'อัปเดตสถานะออเดอร์ #{order_id} สำเร็จ'})
    return jsonify({'status': 'error', 'message': 'ไม่สามารถอัปเดตข้อมูลบน Firebase ได้'}), 500

@app.route('/staff/menu-manage')
@staff_required
def staff_menu_manage():
    menus = get_all_menus()
    return render_template('staff/menu_manage.html', menus=menus)

@app.route('/staff/menu/quick-update/<menu_id>', methods=['POST'])
@staff_required
def quick_update_menu(menu_id):
    data = request.get_json()
    update_fields = {}
    
    if 'price' in data and data['price'] is not None:
        update_fields['price'] = float(data['price'])
    if 'stock' in data:
        stock_val = data['stock']
        update_fields['stock'] = int(stock_val) if (stock_val is not None and stock_val != "") else None
    if 'status' in data:
        update_fields['status'] = data['status']
        
    success = update_menu_item_db(menu_id, update_fields)
    if success:
        return jsonify({'status': 'success', 'message': 'ปรับปรุงข้อมูลเมนูสำเร็จ'})
    return jsonify({'status': 'error', 'message': 'ไม่สามารถอัปเดตข้อมูลได้'}), 500

# ==========================================
# REAL-TIME API FOR ADMIN DASHBOARD
# ==========================================

@app.route('/api/admin/dashboard_stats')
@admin_required
def dashboard_stats():
    conn = get_db_connection()
    cursor = conn.cursor()

    sales_row = cursor.execute('''
        SELECT SUM(total_amount) AS sales 
        FROM orders 
        WHERE DATE(created_at) = DATE('now', 'localtime') AND status = 'completed'
    ''').fetchone()
    sales_today = sales_row['sales'] if sales_row and sales_row['sales'] else 0.0

    cust_row = cursor.execute('''
        SELECT SUM(customer_count) AS cust 
        FROM orders 
        WHERE DATE(created_at) = DATE('now', 'localtime') AND status = 'completed'
    ''').fetchone()
    customers_today = cust_row['cust'] if cust_row and cust_row['cust'] else 0

    # ดึงจำนวน Staff จาก Firebase
    all_users = get_all_users()
    active_staff = sum(
        1 for uid, u in all_users.items() 
        if isinstance(u, dict) and u.get('role') == 'staff' and u.get('is_active')
    )

    conn.close()

    return jsonify({
        'sales_today': round(sales_today, 2),
        'customers_today': customers_today,
        'active_staff': active_staff
    })

# ==========================================
# ADMIN: MENU MANAGEMENT (CRUD)
# ==========================================

@app.route('/admin/menu')
@admin_required
def admin_menu_list():
    conn = get_db_connection()
    menus = conn.execute('SELECT * FROM menus').fetchall()
    conn.close()
    return render_template('admin/menu.html', menus=menus)

@app.route('/admin/menu/add', methods=['POST'])
@admin_required
def admin_menu_add():
    try:
        name = request.form['name'].strip()
        category = request.form['category']
        price = float(request.form['price'])
        spice_level = request.form.get('spice_level', 'ไม่เผ็ด')
        size = request.form.get('size', 'ปกติ')
        status = request.form.get('status', 'available')

        image_filename = None
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            filename = secure_filename(f"menu_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            image_filename = filename

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO menus (name, category, price, spice_level, size, status, image_file)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, category, price, spice_level, size, status, image_filename))
        conn.commit()
        conn.close()

        flash("เพิ่มรายการอาหารเรียบร้อยแล้ว", "success")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาดในการเพิ่มเมนู: {str(e)}", "error")
        
    return redirect(url_for('admin_menu_list'))

@app.route('/admin/menu/edit/<int:id>', methods=['POST'])
@admin_required
def admin_menu_edit(id):
    try:
        name = request.form['name'].strip()
        category = request.form['category']
        price = float(request.form['price'])
        spice_level = request.form.get('spice_level')
        size = request.form.get('size')
        status = request.form.get('status')

        file = request.files.get('image')
        conn = get_db_connection()

        if file and allowed_file(file.filename):
            filename = secure_filename(f"menu_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            conn.execute('''
                UPDATE menus 
                SET name=?, category=?, price=?, spice_level=?, size=?, status=?, image_file=?
                WHERE id=?
            ''', (name, category, price, spice_level, size, status, filename, id))
        else:
            conn.execute('''
                UPDATE menus 
                SET name=?, category=?, price=?, spice_level=?, size=?, status=?
                WHERE id=?
            ''', (name, category, price, spice_level, size, status, id))

        conn.commit()
        conn.close()
        flash("อัปเดตรายการอาหารสำเร็จ", "success")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาดในการแก้ไข: {str(e)}", "error")

    return redirect(url_for('admin_menu_list'))

@app.route('/admin/menu/delete/<int:id>', methods=['POST'])
@admin_required
def admin_menu_delete(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM menus WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'ลบเมนูเรียบร้อยแล้ว'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# ADMIN: STAFF MANAGEMENT (เชื่อมต่อ auth_utils/Firebase)
# ==========================================

@app.route('/admin/staff')
@admin_required
def admin_staff_list():
    users_dict = get_all_users()
    staff_members = []
    for uid, user in users_dict.items():
        if isinstance(user, dict) and user.get('role') != 'customer':
            user['id'] = uid
            staff_members.append(user)
            
    return render_template('admin/staff.html', staff_members=staff_members)

@app.route('/admin/staff/add', methods=['POST'])
@admin_required
def admin_staff_add():
    try:
        username = request.form['username'].strip()
        password = request.form['password'].strip()
        role = request.form.get('role', 'staff')

        # ตรวจสอบชื่อผู้ใช้ซ้ำบน Firebase
        users = get_all_users()
        is_duplicate = any(
            info.get('username') == username 
            for uid, info in users.items() if isinstance(info, dict)
        )
        if is_duplicate:
            flash("ชื่อผู้ใช้นี้มีในระบบแล้ว", "error")
            return redirect(url_for('admin_staff_list'))

        # บันทึกพนักงานลง Firebase ผ่าน auth_utils
        if create_user(username, password, role):
            flash("เพิ่มพนักงานเข้าสู่ Firebase สำเร็จ", "success")
        else:
            flash("เกิดข้อผิดพลาดในการบันทึกพนักงานลง Firebase", "error")

    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")

    return redirect(url_for('admin_staff_list'))

@app.route('/admin/staff/edit/<id>', methods=['POST'])
@admin_required
def admin_staff_edit(id):
    try:
        # โค้ดสำหรับอัปเดตข้อมูลพนักงาน (หากต้องการเขียนเพิ่มทีหลังสามารถใส่ในส่วนนี้ได้)
        
        flash("อัปเดตข้อมูลพนักงานสำเร็จ", "success")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")
        
    return redirect(url_for('admin_staff_list'))

@app.route('/admin/staff/delete/<id>', methods=['POST'])
@admin_required
def admin_staff_delete(id):
    try:
        # โค้ดสำหรับลบพนักงาน (หากต้องการเขียนเพิ่มทีหลังสามารถใส่ในส่วนนี้ได้)
        
        return jsonify({'status': 'success', 'message': 'ลบพนักงานเรียบร้อยแล้ว'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# ADMIN: PAYMENT CHANNELS MANAGEMENT
# ==========================================

@app.route('/admin/payments')
@admin_required
def admin_payments_list():
    conn = get_db_connection()
    payments = conn.execute('SELECT * FROM payment_channels').fetchall()
    conn.close()
    return render_template('admin/payment.html', payments=payments)

@app.route('/admin/payments/add', methods=['POST'])
@admin_required
def admin_payments_add():
    try:
        bank_name = request.form['bank_name'].strip()
        account_name = request.form['account_name'].strip()
        promptpay_no = request.form['promptpay_no'].strip()
        is_active = 1 if request.form.get('is_active') == 'on' else 0

        file = request.files.get('qr_image')
        if not file or not allowed_file(file.filename):
            flash("กรุณาอัปโหลดรูปภาพ QR Code ที่ถูกต้อง", "error")
            return redirect(url_for('admin_payments_list'))

        filename = secure_filename(f"qr_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO payment_channels (bank_name, account_name, promptpay_no, qr_image, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (bank_name, account_name, promptpay_no, filename, is_active))
        conn.commit()
        conn.close()

        flash("เพิ่มช่องทางชำระเงินสำเร็จ", "success")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")

    return redirect(url_for('admin_payments_list'))

@app.route('/admin/payments/edit/<int:id>', methods=['POST'])
@admin_required
def admin_payments_edit(id):
    try:
        bank_name = request.form['bank_name'].strip()
        account_name = request.form['account_name'].strip()
        promptpay_no = request.form['promptpay_no'].strip()
        is_active = 1 if request.form.get('is_active') == 'on' else 0

        file = request.files.get('qr_image')
        conn = get_db_connection()

        if file and allowed_file(file.filename):
            filename = secure_filename(f"qr_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
            file.save(os.path.join(app.config['UPLOAD_FOLDER'], filename))
            conn.execute('''
                UPDATE payment_channels 
                SET bank_name=?, account_name=?, promptpay_no=?, qr_image=?, is_active=?
                WHERE id=?
            ''', (bank_name, account_name, promptpay_no, filename, is_active, id))
        else:
            conn.execute('''
                UPDATE payment_channels 
                SET bank_name=?, account_name=?, promptpay_no=?, is_active=?
                WHERE id=?
            ''', (bank_name, account_name, promptpay_no, is_active, id))

        conn.commit()
        conn.close()
        flash("อัปเดตช่องทางชำระเงินสำเร็จ", "success")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")

    return redirect(url_for('admin_payments_list'))

@app.route('/admin/payments/delete/<int:id>', methods=['POST'])
@admin_required
def admin_payments_delete(id):
    try:
        conn = get_db_connection()
        conn.execute('DELETE FROM payment_channels WHERE id = ?', (id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': 'ลบช่องทางชำระเงินเรียบร้อยแล้ว'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# ADMIN: SALES HISTORY & ORDERS
# ==========================================

@app.route('/admin/sales')
@admin_required
def admin_sales_history():
    conn = get_db_connection()
    orders = conn.execute('SELECT * FROM orders ORDER BY created_at DESC').fetchall()
    conn.close()
    return render_template('admin/sales.html', orders=orders)

@app.route('/admin/sales/void/<int:id>', methods=['POST'])
@admin_required
def admin_sales_void(id):
    try:
        conn = get_db_connection()
        conn.execute("UPDATE orders SET status = 'voided' WHERE id = ?", (id,))
        conn.commit()
        conn.close()
        return jsonify({'status': 'success', 'message': f'ยกเลิกรายการสั่งซื้อ #{id} เรียบร้อยแล้ว'})
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# CUSTOMER ROUTES (หน้าร้านสำหรับลูกค้าสั่งอาหาร)
# ==========================================

@app.route('/customer')
def customer_dashboard():
    # ตรวจสอบสิทธิ์ว่าต้องเป็น customer เท่านั้น
    if session.get('role') != 'customer':
        flash("หน้านี้สำหรับลูกค้าเท่านั้น", "error")
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    # ดึงเฉพาะเมนูที่สถานะ available (พร้อมขาย) มาแสดง
    menus = conn.execute("SELECT * FROM menus WHERE status = 'available'").fetchall()
    
    # ดึงช่องทางการชำระเงินที่เปิดใช้งานมาแสดง
    payments = conn.execute("SELECT * FROM payment_channels WHERE is_active = 1").fetchall()
    conn.close()
    
    # แก้ไข path จาก 'customer/dashboard.html' เป็น 'customer/customer.html'
    return render_template('customer/customer.html', menus=menus, payments=payments)

@app.route('/customer/checkout', methods=['POST'])
def customer_checkout():
    if session.get('role') != 'customer':
        return jsonify({'status': 'error', 'message': 'ไม่มีสิทธิ์เข้าถึง'}), 403

    data = request.get_json()
    total_amount = float(data.get('total_amount', 0))
    payment_method = data.get('payment_method', 'เงินสด')
    customer_count = int(data.get('customer_count', 1))
    items = data.get('items', []) 

    if not items:
        return jsonify({'status': 'error', 'message': 'ไม่มีสินค้าในตะกร้า'}), 400

    try:
        # --- เปลี่ยนมาบันทึกลง Firebase แทน SQLite และเก็บ items (หัวข้อ 1, 4, 5) ---
        FIREBASE_URL = "https://webapplication-e7922-default-rtdb.asia-southeast1.firebasedatabase.app"
        url = f"{FIREBASE_URL}/orders.json"
        
        payload = {
            "customer_count": customer_count,
            "total_amount": total_amount,
            "payment_method": payment_method,
            "status": "pending",
            "items": items, # บันทึกรายการอาหารด้วย
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        req_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(url, data=req_data, headers={'Content-Type': 'application/json'}, method='POST')
        
        with urllib.request.urlopen(req) as response:
            if response.status in [200, 201]:
                res_data = json.loads(response.read().decode('utf-8'))
                order_id = res_data.get('name') # Firebase จะสร้าง ID คืนมาให้ในคีย์ 'name'
                
                return jsonify({
                    'status': 'success', 
                    'message': 'สั่งอาหารสำเร็จ! กรุณารอสักครู่', 
                    'order_id': order_id
                })
            else:
                raise Exception("Firebase Error")

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # 1. สร้างบิลออเดอร์ใหม่ (สถานะ pending = รอดำเนินการ)
        cursor.execute('''
            INSERT INTO orders (customer_count, total_amount, payment_method, status, created_at)
            VALUES (?, ?, ?, 'pending', CURRENT_TIMESTAMP)
        ''', (customer_count, total_amount, payment_method))
        
        order_id = cursor.lastrowid # ดึงเลข ID ออเดอร์ล่าสุดที่เพิ่งสร้าง
        
        # (ทางเลือก) หากคุณมีตาราง order_items สำหรับเก็บรายละเอียดว่าสั่งเมนูอะไรบ้าง สามารถวนลูป Insert ตรงนี้ได้
        # for item in items:
        #     cursor.execute('INSERT INTO order_items (order_id, menu_id, qty, price) VALUES (?, ?, ?, ?)', 
        #                    (order_id, item['id'], item['qty'], item['price']))

        conn.commit()
        conn.close()

        return jsonify({
            'status': 'success', 
            'message': 'สั่งอาหารสำเร็จ! กรุณารอสักครู่', 
            'order_id': order_id
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)