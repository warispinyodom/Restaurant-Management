from api.firebase_db import seed_firebase_from_local

if __name__ == "__main__":
    print("กำลังซิงค์ข้อมูลจาก data.json ไปยัง Firebase Realtime Database...")
    result = seed_firebase_from_local()
    print("ผลการทำงาน:", result)