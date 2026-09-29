import requests
import json

# URL จากที่คุณกำหนดมา
FIREBASE_URL = "https://webapplication-e7922-default-rtdb.asia-southeast1.firebasedatabase.app"

def get_data(path: str) -> dict:
    """ดึงข้อมูลจาก Firebase"""
    try:
        response = requests.get(f"{FIREBASE_URL}/{path}.json")
        response.raise_for_status()
        data = response.json()
        return data if data else {}
    except requests.exceptions.RequestException:
        return {} # ซ่อน Traceback ไม่ให้ผู้ใช้เห็น

def post_data(path: str, data: dict) -> str:
    """เพิ่มข้อมูลใหม่ (สร้าง ID อัตโนมัติ)"""
    try:
        response = requests.post(f"{FIREBASE_URL}/{path}.json", json=data)
        response.raise_for_status()
        return response.json().get("name", "")
    except requests.exceptions.RequestException:
        return ""

def put_data(path: str, data: dict) -> bool:
    """อัปเดตข้อมูลแบบเจาะจง"""
    try:
        response = requests.put(f"{FIREBASE_URL}/{path}.json", json=data)
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False

def delete_data(path: str) -> bool:
    """ลบข้อมูล"""
    try:
        response = requests.delete(f"{FIREBASE_URL}/{path}.json")
        return response.status_code == 200
    except requests.exceptions.RequestException:
        return False