import sqlite3
import os

DB_NAME = "restaurant.db"

def get_db_connection():
    """สร้าง Connection สำหรับเชื่อมต่อกับ SQLite Database"""
    conn = sqlite3.connect(DB_NAME)
    # กำหนด row_factory ให้ดึงข้อมูลมาแล้วเข้าถึงผ่านชื่อคอลัมน์ได้เหมือน Dictionary
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    """สร้างตารางข้อมูล SQLite ในกรณีที่ยังไม่มีตาราง"""
    conn = get_db_connection()
    cursor = conn.cursor()

    # 1. ตารางผู้ใช้งาน / พนักงาน (users)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE NOT NULL,
            password_hash TEXT NOT NULL,
            role TEXT DEFAULT 'staff',
            status TEXT DEFAULT 'active',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # 2. ตารางเมนูอาหาร (menus)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menus (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            price REAL NOT NULL,
            spice_level TEXT,
            size TEXT,
            status TEXT DEFAULT 'available',
            image_file TEXT
        )
    ''')

    # 3. ตารางช่องทางชำระเงิน (payment_channels)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS payment_channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            bank_name TEXT NOT NULL,
            account_name TEXT NOT NULL,
            promptpay_no TEXT NOT NULL,
            qr_image TEXT NOT NULL,
            is_active INTEGER DEFAULT 1
        )
    ''')

    # 4. ตารางประวัติการขาย (orders)
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            total_amount REAL NOT NULL,
            customer_count INTEGER DEFAULT 1,
            status TEXT DEFAULT 'completed',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    conn.commit()
    conn.close()