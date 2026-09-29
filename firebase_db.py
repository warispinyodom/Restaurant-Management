import requests

# ⚠️ อย่าลืมเปลี่ยน URL นี้ให้ตรงกับ Realtime Database ของคุณใน Firebase Console
FIREBASE_URL = "https://your-project-id-default-rtdb.firebaseio.com"

def get_data(node):
    try:
        response = requests.get(f"{FIREBASE_URL}/{node}.json", timeout=5)
        if response.status_code == 200:
            res = response.json()
            return res if isinstance(res, dict) else {}
        return {}
    except Exception as e:
        print(f"[Firebase Get Error]: {e}")
        return {}

def post_data(node, data):
    try:
        response = requests.post(f"{FIREBASE_URL}/{node}.json", json=data, timeout=5)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"[Firebase Post Error]: {e}")
        return None

def patch_data(node, data):
    try:
        response = requests.patch(f"{FIREBASE_URL}/{node}.json", json=data, timeout=5)
        return response.json() if response.status_code == 200 else None
    except Exception as e:
        print(f"[Firebase Patch Error]: {e}")
        return None

def delete_data(node):
    try:
        response = requests.delete(f"{FIREBASE_URL}/{node}.json", timeout=5)
        return response.status_code == 200
    except Exception as e:
        print(f"[Firebase Delete Error]: {e}")
        return False