import os
import ssl
import urllib.request
import urllib.parse
import json
import uuid
from functools import wraps
from datetime import datetime, date, timedelta
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from werkzeug.utils import secure_filename
from werkzeug.security import generate_password_hash, check_password_hash

# ----------------------------------------------------
# Firebase Admin SDK Setup (สำหรับจัดการ Storage)
# ----------------------------------------------------
import firebase_admin
from firebase_admin import credentials, storage

# ตั้งค่า Bucket โดยไม่ต้องมี gs:// หรือโฟลเดอร์ต่อท้าย
FIREBASE_BUCKET = "webapplication-e7922.firebasestorage.app"

# เริ่มต้น Firebase Admin SDK (รองรับทั้ง Vercel Environment Variable และ Local File)
if not firebase_admin._apps:
    cred = None
    
    # 1. ตรวจสอบ Environment Variable สำหรับ Vercel/Production
    service_account_env = os.environ.get('FIREBASE_SERVICE_ACCOUNT')
    if service_account_env:
        try:
            cred_dict = json.loads(service_account_env)
            # แก้ไขปัญหา Newline (\n) ใน Private Key บน Vercel
            if 'private_key' in cred_dict:
                cred_dict['private_key'] = cred_dict['private_key'].replace('\\n', '\n')
            cred = credentials.Certificate(cred_dict)
        except Exception as e:
            print(f"Error parsing FIREBASE_SERVICE_ACCOUNT: {e}")

    # 2. หากไม่มี Env Variable ให้ดึงจากไฟล์ serviceAccountKey.json สำหรับ Local
    if not cred:
        cred_path = os.path.join(os.path.dirname(__file__), "serviceAccountKey.json")
        if os.path.exists(cred_path):
            cred = credentials.Certificate(cred_path)

    # 3. Initialize Firebase App
    if cred:
        firebase_admin.initialize_app(cred, {
            'storageBucket': FIREBASE_BUCKET
        })
    else:
        firebase_admin.initialize_app(options={
            'storageBucket': FIREBASE_BUCKET
        })

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

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'webp'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_firebase_storage(file, folder="uploads"):
    """ฟังก์ชันอัปโหลดไฟล์รูปภาพไปยัง Firebase Storage ผ่าน Firebase Admin SDK"""
    try:
        if not file or not file.filename:
            return None
            
        extension = file.filename.rsplit('.', 1)[1].lower() if '.' in file.filename else 'jpg'
        unique_filename = f"{folder}_{datetime.now().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex[:8]}.{extension}"
        storage_path = f"{folder}/{unique_filename}"
        
        # เชื่อมต่อ Storage Bucket
        bucket = storage.bucket()
        blob = bucket.blob(storage_path)
        
        content_type = file.content_type or 'image/jpeg'
        blob.upload_from_string(file.read(), content_type=content_type)
        
        # สร้าง URL ของ Firebase Storage โดยตรง
        encoded_path = urllib.parse.quote(storage_path, safe='')
        firebase_url = f"https://firebasestorage.googleapis.com/v0/b/{bucket.name}/o/{encoded_path}?alt=media"
        
        return firebase_url
    except Exception as e:
        print(f"Firebase Storage Upload Error: {e}")
        return None

def delete_from_firebase_storage(image_url):
    """ฟังก์ชันลบไฟล์รูปภาพออกจาก Firebase Storage โดยสกัดหา Storage Path จาก URL"""
    try:
        if not image_url or not isinstance(image_url, str):
            return False
            
        if "/o/" in image_url:
            path_part = image_url.split("/o/")[1].split("?")[0]
            storage_path = urllib.parse.unquote(path_part)
            
            bucket = storage.bucket()
            blob = bucket.blob(storage_path)
            
            if blob.exists():
                blob.delete()
                print(f"Successfully deleted {storage_path} from Firebase Storage")
                return True
    except Exception as e:
        print(f"Firebase Storage Delete Error: {e}")
    return False

# ==========================================
# Firebase RTDB Helper Functions
# ==========================================
def get_firebase_data(path):
    try:
        url = f"{FIREBASE_URL}/{path}.json"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, context=ssl_context) as response:
            data = json.loads(response.read().decode('utf-8'))
            return data if data else {}
    except Exception as e:
        print(f"Error fetching {path}: {e}")
        return {}

def post_firebase_data(path, payload):
    try:
        url = f"{FIREBASE_URL}/{path}.json"
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), 
                                     headers={'Content-Type': 'application/json'}, method='POST')
        with urllib.request.urlopen(req, context=ssl_context) as response:
            return json.loads(response.read().decode('utf-8'))
    except Exception as e:
        print(f"Error posting {path}: {e}")
        return None

def patch_firebase_data(path, item_id, payload):
    try:
        url = f"{FIREBASE_URL}/{path}/{item_id}.json"
        req = urllib.request.Request(url, data=json.dumps(payload).encode('utf-8'), 
                                     headers={'Content-Type': 'application/json'}, method='PATCH')
        with urllib.request.urlopen(req, context=ssl_context) as response:
            return response.status == 200
    except Exception as e:
        print(f"Error patching {path}/{item_id}: {e}")
        return False

def delete_firebase_data(path, item_id):
    try:
        url = f"{FIREBASE_URL}/{path}/{item_id}.json"
        req = urllib.request.Request(url, method='DELETE')
        with urllib.request.urlopen(req, context=ssl_context) as response:
            return response.status == 200
    except Exception as e:
        print(f"Error deleting {path}/{item_id}: {e}")
        return False

def parse_firebase_data(data):
    """แปลงข้อมูลจาก Firebase ให้เป็น List อย่างปลอดภัย"""
    if isinstance(data, dict):
        return [{'id': str(k), **v} for k, v in data.items() if isinstance(v, dict)]
    elif isinstance(data, list):
        return [{'id': str(i), **v} for i, v in enumerate(data) if v and isinstance(v, dict)]
    return []

# ==========================================
# Guards
# ==========================================
def admin_required(func_route):
    @wraps(func_route)
    def wrapper(*args, **kwargs):
        if session.get('role') != 'admin':
            flash("คุณไม่มีสิทธิ์เข้าถึงหน้านี้", "error")
            return redirect(url_for('home'))
        return func_route(*args, **kwargs)
    return wrapper

def staff_required(func_route):
    @wraps(func_route)
    def wrapper(*args, **kwargs):
        if session.get('role') not in ['staff', 'admin']:
            flash("คุณไม่มีสิทธิ์เข้าถึงหน้าพนักงาน", "error")
            return redirect(url_for('home'))
        return func_route(*args, **kwargs)
    return wrapper

# ==========================================
# AUTHENTICATION ROUTES
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

            users = get_all_users()
            if not isinstance(users, dict):
                users = {}

            is_duplicate = any(info.get('username') == username for uid, info in users.items() if isinstance(info, dict))
            if is_duplicate:
                flash("ชื่อผู้ใช้นี้มีในระบบแล้ว", "error")
                return redirect(url_for('signup'))

            is_valid, msg = validate_registration(username, password, role)
            if not is_valid:
                flash(msg, "error")
                return redirect(url_for('signup'))

            hashed_password = generate_password_hash(password)
            
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

@app.route('/staff/orders')
@staff_required
def staff_orders():
    try:
        staff_status = session.get('staff_status', 'ready')
        orders = get_all_orders()
        if not isinstance(orders, list):
            orders = []
        return render_template('staff/orders.html', orders=orders, staff_status=staff_status)
    except Exception as e:
        print(f"Error in staff_orders: {e}")
        return render_template('staff/orders.html', orders=[], staff_status='ready')

@app.route('/staff/order/update-status/<order_id>', methods=['POST'])
@staff_required
def update_order_status(order_id):
    try:
        data = request.get_json() or {}
        new_status = data.get('status')
        if not new_status:
            return jsonify({'status': 'error', 'message': 'ไม่พบข้อมูลสถานะใหม่'}), 400

        if update_order_status_db(order_id, new_status):
            return jsonify({'status': 'success', 'message': 'อัปเดตสถานะออเดอร์สำเร็จ'})
        else:
            return jsonify({'status': 'error', 'message': 'ไม่สามารถอัปเดตข้อมูลในฐานข้อมูลได้'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/staff/status/update', methods=['POST'])
@staff_required
def update_staff_status():
    data = request.get_json() or {}
    new_status = data.get('status', 'ready')
    session['staff_status'] = new_status
    return jsonify({'status': 'success', 'message': f'เปลี่ยนสถานะพนักงานเป็น {new_status} สำเร็จ'})

@app.route('/admin/staff/toggle-status/<user_id>', methods=['POST'])
@admin_required
def admin_staff_toggle_status(user_id):
    try:
        target_user = get_firebase_data(f"users/{user_id}")
        
        if target_user.get('role') == 'admin':
            return jsonify({'status': 'error', 'message': 'ไม่สามารถเปลี่ยนสถานะผู้ดูแลระบบได้!'}), 400

        current_status = target_user.get('is_active', True)
        new_status = not current_status

        if patch_firebase_data('users', user_id, {"is_active": new_status}):
            status_text = "เปิดใช้งาน" if new_status else "ถูกระงับ"
            return jsonify({'status': 'success', 'message': f'เปลี่ยนสถานะบัญชีเป็น "{status_text}" เรียบร้อยแล้ว'})

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
        menus = get_all_menus()
        if not isinstance(menus, list):
            menus = []
    except Exception as e:
        print(f"Error loading staff menus: {e}")
        menus = []
        flash(f"เกิดข้อผิดพลาดในการโหลดข้อมูลเมนู: {str(e)}", "error") 

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
        
    if update_menu_item_db(menu_id, update_fields):
        return jsonify({'status': 'success', 'message': 'ปรับปรุงข้อมูลเมนูสำเร็จ'})
    return jsonify({'status': 'error', 'message': 'ไม่สามารถอัปเดตข้อมูลได้'}), 500

# ==========================================
# REAL-TIME API FOR ADMIN DASHBOARD
# ==========================================
@app.route('/api/admin/dashboard_stats')
@admin_required
def dashboard_stats():
    today = datetime.now()
    today_str = today.strftime("%Y-%m-%d")
    
    start_of_week = today - timedelta(days=today.weekday())
    
    weekly_sales = [0.0] * 7
    sales_today = 0.0
    customers_today = 0
    
    orders = get_all_orders()
    order_items = orders if isinstance(orders, list) else (orders.values() if isinstance(orders, dict) else [])
    
    for order in order_items:
        if isinstance(order, dict):
            created_at = order.get('created_at', '')
            status = order.get('status', '')
            
            if status in ['completed', 'paid']:
                amount = float(order.get('total_amount', 0))
                
                if created_at.startswith(today_str):
                    sales_today += amount
                    customers_today += int(order.get('customer_count', 0))
                
                if created_at:
                    try:
                        order_date = datetime.strptime(created_at.split(' ')[0], "%Y-%m-%d")
                        delta_days = (order_date.date() - start_of_week.date()).days
                        if 0 <= delta_days < 7:
                            weekly_sales[delta_days] += amount
                    except Exception:
                        pass

    all_users = get_all_users()
    active_staff = 0
    if isinstance(all_users, dict):
        active_staff = sum(
            1 for uid, u in all_users.items() 
            if isinstance(u, dict) and u.get('role') in ['staff', 'admin'] and u.get('is_active', True)
        )

    return jsonify({
        'sales_today': round(sales_today, 2),
        'customers_today': customers_today,
        'active_staff': active_staff,
        'weekly_sales': [round(x, 2) for x in weekly_sales]
    })
    
# ==========================================
# ADMIN: MENU MANAGEMENT
# ==========================================
@app.route('/admin/menu')
@admin_required
def admin_menu_list():
    try:
        raw_menus = get_firebase_data('menus')
        menus = parse_firebase_data(raw_menus)
    except Exception as e:
        print(f"Error loading admin menus: {e}")
        menus = []
        flash("เกิดข้อผิดพลาดในการโหลดข้อมูลเมนู", "error")
        
    return render_template('admin/menu.html', menus=menus)

@app.route('/admin/menu/add', methods=['POST'])
@admin_required
def admin_menu_add():
    # ตรวจสอบว่าเป็น AJAX Call (เช่น จาก fetch) หรือไม่
    is_ajax = (
        request.headers.get('X-Requested-With') == 'XMLHttpRequest' or
        'application/json' in request.headers.get('Accept', '')
    )
    try:
        name = request.form.get('name', '').strip()
        category = request.form.get('category', '').strip()
        
        if not name or not category:
            if is_ajax:
                return jsonify({'status': 'error', 'message': 'กรุณากรอกชื่อและหมวดหมู่เมนู'}), 400
            flash("กรุณากรอกชื่อและหมวดหมู่เมนู", "error")
            return redirect(url_for('admin_menu_list'))

        raw_price = request.form.get('price', 0)
        try:
            price = float(raw_price)
        except (ValueError, TypeError):
            price = 0.0

        payload = {
            'name': name,
            'category': category,
            'price': price,
            'spice_level': request.form.get('spice_level', 'ไม่เผ็ด'),
            'size': request.form.get('size', 'ปกติ'),
            'status': request.form.get('status', 'available'),
            'image_file': None
        }

        file = request.files.get('image')
        if file and allowed_file(file.filename):
            payload['image_file'] = upload_to_firebase_storage(file, folder="menus")

        if post_firebase_data('menus', payload):
            if is_ajax:
                return jsonify({'status': 'success', 'message': 'เพิ่มรายการอาหารเรียบร้อยแล้ว'})
            flash("เพิ่มรายการอาหารเรียบร้อยแล้ว", "success")
        else:
            if is_ajax:
                return jsonify({'status': 'error', 'message': 'เกิดข้อผิดพลาดในการบันทึกข้อมูล'}), 500
            flash("เกิดข้อผิดพลาดในการเพิ่มรายการอาหาร", "error")
    except Exception as e:
        if is_ajax:
            return jsonify({'status': 'error', 'message': str(e)}), 500
        flash(f"เกิดข้อผิดพลาดในการเพิ่มเมนู: {str(e)}", "error")
        
    return redirect(url_for('admin_menu_list'))

@app.route('/admin/menu/edit/<id>', methods=['POST'])
@admin_required
def admin_menu_edit(id):
    try:
        payload = {
            'name': request.form['name'].strip(),
            'category': request.form['category'],
            'price': float(request.form['price']),
            'status': request.form.get('status', 'available')
        }

        # อัปเดตเฉพาะฟิลด์ที่มีการส่งค่าเข้ามาเท่านั้น
        if 'spice_level' in request.form:
            payload['spice_level'] = request.form.get('spice_level')
        if 'size' in request.form:
            payload['size'] = request.form.get('size')

        file = request.files.get('image')
        if file and allowed_file(file.filename):
            old_menu = get_firebase_data(f'menus/{id}')
            if old_menu and isinstance(old_menu, dict) and old_menu.get('image_file'):
                delete_from_firebase_storage(old_menu['image_file'])

            payload['image_file'] = upload_to_firebase_storage(file, folder="menus")

        if patch_firebase_data('menus', id, payload):
            flash("อัปเดตรายการอาหารสำเร็จ", "success")
        else:
            flash("เกิดข้อผิดพลาดในการแก้ไขรายการอาหาร", "error")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาดในการแก้ไข: {str(e)}", "error")

    return redirect(url_for('admin_menu_list'))

@app.route('/admin/menu/delete/<id>', methods=['POST'])
@admin_required
def admin_menu_delete(id):
    try:
        menu = get_firebase_data(f'menus/{id}')
        if menu and isinstance(menu, dict) and menu.get('image_file'):
            delete_from_firebase_storage(menu['image_file'])

        if delete_firebase_data('menus', id):
            return jsonify({'status': 'success', 'message': 'ลบเมนูเรียบร้อยแล้ว'})
        return jsonify({'status': 'error', 'message': 'เกิดข้อผิดพลาดในการลบ'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/menu/batch-delete', methods=['POST'])
@admin_required
def admin_menu_batch_delete():
    """ลบรายการเมนูทีละหลายรายการพร้อมกัน (Batch Delete)"""
    try:
        data = request.get_json() or {}
        ids = data.get('ids', [])
        if not ids:
            return jsonify({'status': 'error', 'message': 'ไม่พบรายการที่ต้องการลบ'}), 400

        deleted_count = 0
        for menu_id in ids:
            # ลบรูปภาพออกจาก Firebase Storage ก่อนถ้ามี
            menu = get_firebase_data(f'menus/{menu_id}')
            if menu and isinstance(menu, dict) and menu.get('image_file'):
                delete_from_firebase_storage(menu['image_file'])
            
            # ลบข้อมูลใน Realtime Database
            if delete_firebase_data('menus', menu_id):
                deleted_count += 1

        return jsonify({
            'status': 'success',
            'message': f'ลบรายการเมนูเรียบร้อยแล้ว {deleted_count} รายการ'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

@app.route('/admin/menu/batch-edit', methods=['POST'])
@admin_required
def admin_menu_batch_edit():
    """แก้ไขรายการเมนูทีละหลายรายการพร้อมกัน (Batch Edit)"""
    try:
        data = request.get_json() or {}
        ids = data.get('ids', [])
        if not ids:
            return jsonify({'status': 'error', 'message': 'ไม่พบรายการที่เลือก'}), 400

        payload = {}
        if data.get('category'):
            payload['category'] = data['category']
        if data.get('status'):
            payload['status'] = data['status']
        if data.get('price') is not None:
            try:
                payload['price'] = abs(float(data['price']))
            except (ValueError, TypeError):
                pass

        if not payload:
            return jsonify({'status': 'error', 'message': 'ไม่มีข้อมูลใหม่ที่ต้องอัปเดต'}), 400

        updated_count = 0
        for menu_id in ids:
            if patch_firebase_data('menus', menu_id, payload):
                updated_count += 1

        return jsonify({
            'status': 'success',
            'message': f'อัปเดตรายการเมนูเรียบร้อยแล้ว {updated_count} รายการ'
        })
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# ADMIN: STAFF MANAGEMENT
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

        is_duplicate = any(info.get('username') == username for uid, info in users.items() if isinstance(info, dict))
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

        if patch_firebase_data('users', user_id, update_data):
            flash("อัปเดตข้อมูลพนักงานสำเร็จ", "success")
        else:
            flash("ไม่สามารถอัปเดตข้อมูลไปยัง Firebase ได้", "error")

    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")

    return redirect(url_for('admin_staff_list'))

@app.route('/admin/staff/delete/<id>', methods=['POST'])
@admin_required
def admin_staff_delete(id):
    try:
        if delete_firebase_data('users', id):
            return jsonify({'status': 'success', 'message': 'ลบพนักงานเรียบร้อยแล้ว'})
        return jsonify({'status': 'error', 'message': 'เกิดข้อผิดพลาดในการลบ'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# ADMIN: PAYMENT CHANNELS MANAGEMENT
# ==========================================
@app.route('/admin/payments')
@admin_required
def admin_payments_list():
    raw_payments = get_firebase_data('payment_channels')
    payments = parse_firebase_data(raw_payments)
    return render_template('admin/payment.html', payments=payments)

@app.route('/admin/payments/add', methods=['POST'])
@admin_required
def admin_payments_add():
    try:
        payload = {
            'bank_name': request.form['bank_name'].strip(),
            'account_name': request.form['account_name'].strip(),
            'promptpay_no': request.form['promptpay_no'].strip(),
            'is_active': 1 if request.form.get('is_active') == 'on' else 0,
            'qr_image': None
        }

        file = request.files.get('qr_image')
        if not file or not allowed_file(file.filename):
            flash("กรุณาอัปโหลดรูปภาพ QR Code ที่ถูกต้อง", "error")
            return redirect(url_for('admin_payments_list'))

        payload['qr_image'] = upload_to_firebase_storage(file, folder="payments")

        if post_firebase_data('payment_channels', payload):
            flash("เพิ่มช่องทางชำระเงินสำเร็จ", "success")
        else:
            flash("เกิดข้อผิดพลาดในการเพิ่มช่องทาง", "error")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")

    return redirect(url_for('admin_payments_list'))

@app.route('/admin/payments/edit/<id>', methods=['POST'])
@admin_required
def admin_payments_edit(id):
    try:
        payload = {
            'bank_name': request.form['bank_name'].strip(),
            'account_name': request.form['account_name'].strip(),
            'promptpay_no': request.form['promptpay_no'].strip(),
            'is_active': 1 if request.form.get('is_active') == 'on' else 0
        }

        file = request.files.get('qr_image')
        if file and allowed_file(file.filename):
            payload['qr_image'] = upload_to_firebase_storage(file, folder="payments")

        if patch_firebase_data('payment_channels', id, payload):
            flash("อัปเดตช่องทางชำระเงินสำเร็จ", "success")
        else:
            flash("เกิดข้อผิดพลาดในการอัปเดตช่องทาง", "error")
    except Exception as e:
        flash(f"เกิดข้อผิดพลาด: {str(e)}", "error")

    return redirect(url_for('admin_payments_list'))

@app.route('/admin/payments/delete/<id>', methods=['POST'])
@admin_required
def admin_payments_delete(id):
    try:
        if delete_firebase_data('payment_channels', id):
            return jsonify({'status': 'success', 'message': 'ลบช่องทางชำระเงินเรียบร้อยแล้ว'})
        return jsonify({'status': 'error', 'message': 'เกิดข้อผิดพลาดในการลบ'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# ADMIN: SALES HISTORY & ORDERS
# ==========================================
@app.route('/admin/sales')
@admin_required
def admin_sales_history():
    raw_orders = get_firebase_data('orders')
    orders = parse_firebase_data(raw_orders)
    orders.sort(key=lambda x: x.get('created_at', ''), reverse=True)
    return render_template('admin/sales.html', orders=orders)

@app.route('/admin/sales/void/<id>', methods=['POST'])
@admin_required
def admin_sales_void(id):
    try:
        if patch_firebase_data('orders', id, {'status': 'voided'}):
            return jsonify({'status': 'success', 'message': f'ยกเลิกรายการสั่งซื้อเรียบร้อยแล้ว'})
        return jsonify({'status': 'error', 'message': 'เกิดข้อผิดพลาดในการยกเลิกออเดอร์'}), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

# ==========================================
# CUSTOMER ROUTES 
# ==========================================
@app.route('/customer')
def customer_dashboard():
    if session.get('role') != 'customer':
        flash("หน้านี้สำหรับลูกค้าเท่านั้น", "error")
        return redirect(url_for('home'))
    
    try:
        raw_menus = get_firebase_data('menus')
        menus = [m for m in parse_firebase_data(raw_menus) if m.get('status') == 'available']
        
        raw_payments = get_firebase_data('payment_channels')
        payments = [p for p in parse_firebase_data(raw_payments) if p.get('is_active') == 1]
    except Exception as e:
        print(f"Error loading customer data: {e}")
        menus, payments = [], []
        flash("เกิดข้อผิดพลาดในการโหลดข้อมูลร้านค้า กรุณารีเฟรชหน้าเว็บ", "error")
    
    return render_template('customer/customer.html', menus=menus, payments=payments)

@app.route('/customer/checkout', methods=['POST'])
def customer_checkout():
    if session.get('role') != 'customer':
        return jsonify({'status': 'error', 'message': 'ไม่มีสิทธิ์เข้าถึง'}), 403

    data = request.get_json() or {}
    table_no = data.get('table_no', '-')

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
        payload = {
            "table_no": table_no,
            "customer_count": customer_count,
            "total_amount": total_amount,
            "payment_method": payment_method,
            "status": "pending",
            "items": items,
            "created_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        }
        
        response = post_firebase_data('orders', payload)
        if response and 'name' in response:
            return jsonify({
                'status': 'success', 
                'message': 'สั่งอาหารสำเร็จ! กรุณารอสักครู่', 
                'order_id': response.get('name')
            })
        else:
            raise Exception("Firebase Response Error")

    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)