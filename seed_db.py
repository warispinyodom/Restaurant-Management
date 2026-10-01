import json
import urllib.request

FIREBASE_URL = "https://webapplication-e7922-default-rtdb.asia-southeast1.firebasedatabase.app"

# ข้อมูลเริ่มต้นสำหรับทดสอบระบบ
initial_data = {
    "users": {
        "usr_admin01": {
            "username": "admin01",
            "password": "password123",
            "role": "admin",
            "is_active": True
        },
        "usr_staff01": {
            "username": "staff01",
            "password": "password123",
            "role": "staff",
            "is_active": True
        }
    },
    "categories": {
        "cat_01": { "name": "Pasta", "display_order": 1 },
        "cat_02": { "name": "Pizza", "display_order": 2 },
        "cat_03": { "name": "Drinks", "display_order": 3 }
    },
    "menu_items": {
        "menu_01": {
            "name": "Spaghetti Carbonara",
            "category_id": "cat_01",
            "price": 250.0,
            "image_url": "https://images.unsplash.com/photo-1612874742237-6526221588e3",
            "is_available": True
        },
        "menu_02": {
            "name": "Pizza Margherita",
            "category_id": "cat_02",
            "price": 320.0,
            "image_url": "https://images.unsplash.com/photo-1604382354936-07c5d9983bd3",
            "is_available": True
        }
    },
    "tables": {
        "tbl_01": { "table_number": 1, "capacity": 4, "status": "available", "current_order_id": None },
        "tbl_02": { "table_number": 2, "capacity": 2, "status": "available", "current_order_id": None },
        "tbl_03": { "table_number": 3, "capacity": 6, "status": "available", "current_order_id": None }
    }
}

def seed_database():
    url = f"{FIREBASE_URL}/.json"
    data = json.dumps(initial_data).encode('utf-8')
    try:
        req = urllib.request.Request(
            url, 
            data=data, 
            headers={'Content-Type': 'application/json'}, 
            method='PUT' # ใช้ PUT เพื่อทับรากของ Database ด้วย Initial Data
        )
        with urllib.request.urlopen(req) as response:
            if response.status == 200:
                print(" Successfully initialized Firebase Database!")
            else:
                print(f" Failed with status code: {response.status}")
    except Exception as e:
        print(f" Error connecting to Firebase: {e}")

if __name__ == '__main__':
    seed_database()