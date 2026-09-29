import json
import os

DATA_FILE = os.path.join(os.path.dirname(__file__), '..', 'data.json')

def load_local_data():
    """อ่านข้อมูลจากไฟล์ JSON ท้องถิ่นด้วย open()"""
    try:
        if not os.path.exists(DATA_FILE):
            return {}
        with open(DATA_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return {}

def save_local_data(data):
    """บันทึกข้อมูลลงไฟล์ JSON ท้องถิ่นด้วย open() และ write"""
    try:
        with open(DATA_FILE, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            return True
    except Exception:
        return False