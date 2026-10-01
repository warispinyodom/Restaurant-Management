import os
import sqlite3
import ssl
import urllib.request
import urllib.parse
import json
from functools import wraps
from datetime import datetime, date
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ตั้งค่าชื่อ Firebase Storage Bucket
FIREBASE_BUCKET = "webapplication-e7922.firebasestorage.app"

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

# URL Firebase Realtime Database
FIREBASE_URL = "https://webapplication-e7922-default-rtdb.asia-southeast1.firebasedatabase.app"

# SSL Context สำหรับการเชื่อมต่อ REST API
ssl_context = ssl.create_default_context()
ssl_context.check_hostname = False
ssl_context.verify_mode = ssl.CERT_NONE

# นามสกุลไฟล์ที่อนุญาต
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

# สร้างตารางใน Database อัตโนมัติเมื่อเริ่มระบบ
init_db()

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_firebase_storage(file, folder="uploads"):
    """ฟังก์ชันอัปโหลดไฟล์รูปภาพไปยัง Firebase Storage ผ่าน REST API"""
    try:
        if not file or not file.filename:
            return None
            
        filename = secure_filename(f"{folder}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{file.filename}")
        storage_path = f"{folder}/{filename}"
        encoded_path = urllib.parse.quote(storage_path, safe='')
        
        upload_url = f"https://firebasestorage.googleapis.com/v0/b/{FIREBASE_BUCKET}/o?uploadType=media&name={encoded_path}"
        
        file_data = file.read()
        content_type = file.content_type or 'image/jpeg'
        
        req = urllib.request.Request(
            upload_url,
            data=file_data,
            headers={'Content-Type': content_type},
            method='POST'
        )
        
        with urllib.request.urlopen(req, context=ssl_context) as response:
            if response.status in [200, 201]:
                # ส่งคืน URL สาธารณะของไฟล์บน Firebase Storage
                return f"https://firebasestorage.googleapis.com/v0/b/{FIREBASE_BUCKET}/o/{encoded_path}?alt=media"
    except Exception as e:
        print(f"Firebase Storage Upload Error: {e}")
    return None

# Helper ตรวจสอบสิทธิ์ Admin
def admin_required(func_route):
    @wraps(func_route)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("คุณไม่มีสิทธิ์เข้าถึงหน้านี้", "error")
            return redirect(url_for('home'))
        return func_route(*args, **kwargs)
    return wrapper

# Helper ตรวจสอบสิทธิ์ Staff
def staff_required(func_route):
    @wraps(func_route)
    def wrapper(*args, **kwargs):
        if session.get('role') not in ['staff', 'admin']:
            flash("คุณไม่มีสิทธิ์เข้าถึงหน้าพนักงาน", "error")
            return redirect(url_for('home'))
        return func_route(*args, **kwargs)
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
            username = request.form.get('username', '').strip()
            password = request.form.get('password', '').strip()
            role = 'customer' 

            # ดึงผู้ใช้ทั้งหมดมาเช็คชื่อซ้ำจาก Firebase
            users = get_all_users()
            if not isinstance(users, dict):
                users = {}

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

            # เข้ารหัสผ่านก่อนบันทึก
            hashed_password = generate_password_hash(password)
            
            # บันทึกผู้ใช้ลง Firebase
            if create_user(username, hashed_password, role):
                flash("สมัครสมาชิกสำเร็จ! กรุณาเข้าสู่ระบบ", "success")
                return redirect(url_for('signin'))
            else:
                flash("ไม่สามารถเชื่อมต่อฐานข้อมูล Firebase ได้ กรุณาลองใหม่อีกครั้ง", "error")
                return redirect(url_for('signup'))
                
        except Exception as e:
            flash(f"เกิดข้อผิดพลาดของระบบ: {str(e)}", "error")
            return redirect(url_for('signup'))

    return render_template('signup.html')

@app.route('/signin', methods=['GET', 'POST'])
def signin():
    if request.method == 'POST':
        username = request.form.get('username', '').strip()
        password = request.form.get('password', '').strip()

        is_valid, user_info = check_credentials(username, password)
        
        if is_valid:
            # ตรวจสอบว่าบัญชีถูกระงับหรือไม่
            if not user_info.get('is_active', True):
                flash("บัญชีของคุณถูกระงับการใช้งาน กรุณาติดต่อผู้ดูแลระบบ", "error")
                return render_template('signin.html')

            session['username'] = user_info['username']
            session['role'] = user_info['role']
            session['user_id'] = user_info.get('id', '')
            
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
    return render_template('dashboard.html', username=session.get('username'), role=session.get('role'))

# --- ระบบ Staff (ออเดอร์ / สต็อก / สถานะพนักงาน) ---

@app.route('/staff/orders')
@staff_required
def staff_orders():
    try:
        staff_status = session.get('staff_status', 'ready')
        orders = get_all_orders()
        if orders is None:
            orders = {}
        return render_template('staff/orders.html', orders=orders, staff_status=staff_status)
    except Exception as e:
        flash(f"เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล: {str(e)}", "error")
        return render_template('staff/orders.html', orders={}, staff_status='ready')

@app.route('/staff/status/update', methods=['POST'])
@staff_required
def update_staff_status():
    data = request.get_json() or {}
    new_status = data.get('status', 'ready')
    session['staff_status'] = new_status
    return jsonify({'status': 'success', 'message': f'เปลี่ยนสถานะพนักงานเป็น {new_status} สำเร็จ'})

# ==========================================
# ADMIN: TOGGLE STAFF STATUS (ล็อคไม่ให้ระงับ Admin)
# ==========================================

@app.route('/admin/staff/toggle-status/<user_id>', methods=['POST'])
@admin_required
def admin_staff_toggle_status(user_id):
    try:
        url_get = f"{FIREBASE_URL}/users/{user_id}.json"
        req_get = urllib.request.Request(url_get)
        with urllib.request.urlopen(req_get, context=ssl_context) as response:
            target_user = json.loads(response.read().decode('utf-8')) or {}

        # ตรวจสอบ: ห้ามระงับบัญชีที่เป็น Admin
        if target_user.get('role') == 'admin':
            return jsonify({
                'status': 'error', 
                'message': 'ไม่สามารถเปลี่ยนสถานะหรือระงับบัญชีผู้ดูแลระบบ (Admin) ได้!'
            }), 400

        current_status = target_user.get('is_active', True)
        new_status = not current_status

        url_patch = f"{FIREBASE_URL}/users/{user_id}.json"
        payload = json.dumps({"is_active": new_status}).encode('utf-8')
        req_patch = urllib.request.Request(
            url_patch, 
            data=payload, 
            headers={'Content-Type': 'application/json'}, 
            method='PATCH'
        )
        
        with urllib.request.urlopen(req_patch, context=ssl_context) as response:
            if response.status == 200:
                status_text = "เปิดใช้งาน" if new_status else "ถูกระงับ"
                return jsonify({
                    'status': 'success', 
                    'message': f'เปลี่ยนสถานะบัญชีเป็น "{status_text}" เรียบร้อยแล้ว'
                })

        return jsonify({'status': 'error', 'message': 'ไม่สามารถอัปเดตข้อมูลได้'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# STAFF: MENU MANAGEMENT
# ==========================================

@app.route('/staff/menu-manage')
@staff_required
def staff_menu_manage():
    try:
        conn = get_db_connection()
        raw_menus = conn.execute('SELECT * FROM menus').fetchall()
        conn.close()
        
        menus = [dict(item) for item in raw_menus] if raw_menus else []
    except Exception as e:
        menus = []
        flash(f"เกิดข้อผิดพลาดในการโหลดเมนู: {str(e)}", "error")

    return render_template('staff/menu_manage.html', menus=menus)

@app.route('/staff/menu/quick-update/<menu_id>', methods=['POST'])
@staff_required
def quick_update_menu(menu_id):
    data = request.get_json() or {}
    update_fields = {}
    
    if 'price' in data and data['price'] is not None:
        update_fields['price'] = abs(float(data['price']))
    if 'stock' in data:
        stock_val = data['stock']
        update_fields['stock'] = abs(int(stock_val)) if (stock_val is not None and stock_val != "") else None
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
    today_str = datetime.now().strftime("%Y-%m-%d")
    orders = get_all_orders()
    
    sales_today = 0.0
    customers_today = 0
    
    if isinstance(orders, dict):
        for oid, order in orders.items():
            if isinstance(order, dict):
                created_at = order.get('created_at', '')
                status = order.get('status', '')
                if created_at.startswith(today_str) and status in ['completed', 'paid']:
                    sales_today += float(order.get('total_amount', 0))
                    customers_today += int(order.get('customer_count', 0))

    all_users = get_all_users()
    active_staff = sum(
        1 for uid, u in all_users.items() 
        if isinstance(u, dict) and u.get('role') in ['staff', 'admin'] and u.get('is_active', True)
    )

    return jsonify({
        'sales_today': round(sales_today, 2),
        'customers_today': customers_today,
        'active_staff': active_staff
    })

# ==========================================
# ADMIN: MENU MANAGEMENT (อัปโหลดรูปไป Firebase Storage)
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

        image_url = None
        file = request.files.get('image')
        if file and allowed_file(file.filename):
            image_url = upload_to_firebase_storage(file, folder="menus")

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO menus (name, category, price, spice_level, size, status, image_file)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (name, category, price, spice_level, size, status, image_url))
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
            image_url = upload_to_firebase_storage(file, folder="menus")
            conn.execute('''
                UPDATE menus 
                SET name=?, category=?, price=?, spice_level=?, size=?, status=?, image_file=?
                WHERE id=?
            ''', (name, category, price, spice_level, size, status, image_url, id))
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
# ADMIN: STAFF MANAGEMENT (Firebase)
# ==========================================

@app.route('/admin/staff')
@admin_required
def admin_staff_list():
    users_dict = get_all_users()
    staff_members = []
    if isinstance(users_dict, dict):
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

        if len(username) < 3 or len(password) < 4:
            flash("ชื่อผู้ใช้ต้องมีอย่างน้อย 3 ตัวอักษร และรหัสผ่าน 4 ตัวอักษร", "error")
            return redirect(url_for('admin_staff_list'))

        users = get_all_users()
        if not isinstance(users, dict):
            users = {}

        is_duplicate = any(
            info.get('username') == username 
            for uid, info in users.items() if isinstance(info, dict)
        )
        if is_duplicate:
            flash("ชื่อผู้ใช้นี้มีในระบบแล้ว", "error")
            return redirect(url_for('admin_staff_list'))

        hashed_password = generate_password_hash(password)

        if create_user(username, hashed_password, role):
            flash("เพิ่มพนักงานเข้าสู่ระบบสำเร็จ", "success")
        else:
            flash("เกิดข้อผิดพลาดในการบันทึกพนักงานลง Firebase", "error")

    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")

    return redirect(url_for('admin_staff_list'))

@app.route('/admin/staff/edit/<user_id>', methods=['POST'])
@admin_required
def admin_staff_edit(user_id):
    try:
        username = request.form.get('username', '').strip()
        role = request.form.get('role', 'staff')
        status_input = request.form.get('is_active', 'true')
        password = request.form.get('password', '').strip()

        if role == 'admin':
            is_active = True
        else:
            is_active = True if str(status_input).lower() in ['true', 'on', '1'] else False

        update_data = {
            "role": role,
            "is_active": is_active
        }

        if username:
            update_data["username"] = username

        if password:
            update_data["password"] = generate_password_hash(password)

        url = f"{FIREBASE_URL}/users/{user_id}.json"
        payload = json.dumps(update_data).encode('utf-8')
        req = urllib.request.Request(
            url, 
            data=payload, 
            headers={'Content-Type': 'application/json'}, 
            method='PATCH'
        )
        
        with urllib.request.urlopen(req, context=ssl_context) as response:
            if response.status == 200:
                flash("อัปเดตข้อมูลพนักงานสำเร็จ", "success")
                return redirect(url_for('admin_staff_list'))
                
        flash("ไม่สามารถอัปเดตข้อมูลไปยัง Firebase ได้", "error")

    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")

    return redirect(url_for('admin_staff_list'))

@app.route('/admin/staff/delete/<id>', methods=['POST'])
@admin_required
def admin_staff_delete(id):
    try:
        url = f"{FIREBASE_URL}/users/{id}.json"
        req = urllib.request.Request(url, method='DELETE')
        with urllib.request.urlopen(req, context=ssl_context) as response:
            if response.status == 200:
                return jsonify({'status': 'success', 'message': 'ลบพนักงานเรียบร้อยแล้ว'})
            return jsonify({'status': 'error', 'message': 'เกิดข้อผิดพลาดในการลบ'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# ADMIN: PAYMENT CHANNELS MANAGEMENT (อัปโหลดรูปไป Firebase Storage)
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

        qr_url = upload_to_firebase_storage(file, folder="payments")

        conn = get_db_connection()
        conn.execute('''
            INSERT INTO payment_channels (bank_name, account_name, promptpay_no, qr_image, is_active)
            VALUES (?, ?, ?, ?, ?)
        ''', (bank_name, account_name, promptpay_no, qr_url, is_active))
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
            qr_url = upload_to_firebase_storage(file, folder="payments")
            conn.execute('''
                UPDATE payment_channels 
                SET bank_name=?, account_name=?, promptpay_no=?, qr_image=?, is_active=?
                WHERE id=?
            ''', (bank_name, account_name, promptpay_no, qr_url, is_active, id))
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
    if session.get('role') != 'customer':
        flash("หน้านี้สำหรับลูกค้าเท่านั้น", "error")
        return redirect(url_for('home'))
    
    conn = get_db_connection()
    menus = conn.execute("SELECT * FROM menus WHERE status = 'available'").fetchall()
    payments = conn.execute("SELECT * FROM payment_channels WHERE is_active = 1").fetchall()
    conn.close()
    
    return render_template('customer/customer.html', menus=menus, payments=payments)

@app.route('/customer/checkout', methods=['POST'])
def customer_checkout():
    if session.get('role') != 'customer':
        return jsonify({'status': 'error', 'message': 'ไม่มีสิทธิ์เข้าถึง'}), 403

    data = request.get_json() or {}
    
    raw_total = data.get('total_amount')
    try:
        total_amount = float(raw_total) if raw_total is not None else 0.0
    except (ValueError, TypeError):
        total_amount = 0.0

    raw_count = data.get('customer_count')
    try:
        customer_count = int(raw_count) if raw_count is not None else 1
    except (ValueError, TypeError):
        customer_count = 1

    payment_method = data.get('payment_method', 'เงินสด')
    items = data.get('items', []) 

    if not items:
        return jsonify({'status': 'error', 'message': 'ไม่มีสินค้าในตะกร้า'}), 400

    try:
        url = f"{FIREBASE_URL}/orders.json"
        
        payload = {
            "customer_count": customer_count,
            "total_amount": total_amount,
            "payment_method": payment_method,
            "status": "pending",
            "items": items,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        req_data = json.dumps(payload).encode('utf-8')
        req = urllib.request.Request(
            url, 
            data=req_data, 
            headers={'Content-Type': 'application/json'}, 
            method='POST'
        )
        
        with urllib.request.urlopen(req, context=ssl_context) as response:
            if response.status in [200, 201]:
                res_data = json.loads(response.read().decode('utf-8'))
                order_id = res_data.get('name')
                
                return jsonify({
                    'status': 'success', 
                    'message': 'สั่งอาหารสำเร็จ! กรุณารอสักครู่', 
                    'order_id': order_id
                })
            else:
                raise Exception("Firebase Response Error")

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)