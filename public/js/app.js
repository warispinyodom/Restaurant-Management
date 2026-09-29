// เพิ่มการส่งออเดอร์จริงเข้าสู่ระบบ
async function loginUser(username, password) {
    const response = await fetch('/api/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username, password: password })
    });
    
    const data = await response.json();
    if (data.status === 'success') {
        alert(data.message);
        localStorage.setItem('userRole', data.role); // เก็บสิทธิ์การเข้าใช้งาน
        window.location.href = '/dashboard.html'; // ไปหน้าถัดไป
    } else {
        alert("เข้าสู่ระบบล้มเหลว: " + data.message);
    }
}
async function registerUser(username, password, role="guest") {
    const response = await fetch('/api/register', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ username: username, password: password, role: role })
    });
    
    const data = await response.json();
    if (data.status === 'success') {
        alert("สมัครสมาชิกสำเร็จ! กรุณาล็อคอิน");
    } else {
        alert("สมัครสมาชิกล้มเหลว: " + data.message);
    }
}
async function submitOrder() {
    if (currentCart.length === 0) {
        alert("กรุณาเลือกรายการอาหารก่อนสั่ง");
        return;
    }

    try {
        const res = await fetch('/api/order/create', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                table_id: selectedTable,
                items: currentCart
            })
        });
        const data = await res.json();

        if (res.ok) {
            alert(`สั่งอาหารสำเร็จ! รหัสออเดอร์: ${data.order_id}`);
            currentCart = []; // ล้างตะกร้า
        } else {
            alert(data.error || "เกิดข้อผิดพลาดในการสั่งอาหาร");
        }
    } catch (err) {
        alert("ไม่สามารถเชื่อมต่อเซิร์ฟเวอร์เพื่อส่งออเดอร์ได้");
    }
}

// อัปเดตสถานะอาหารในครัว (สำหรับ Staff)
async function updateKitchenStatus(orderId, newStatus) {
    try {
        const res = await fetch('/api/kitchen/status', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ order_id: orderId, status: newStatus })
        });
        if (res.ok) {
            startKitchenPolling(); // โหลดข้อมูลครัวใหม่ทันที
        }
    } catch (err) {
        console.error("อัปเดตสถานะครัวไม่สำเร็จ", err);
    }
}

// ปุ่ม Sync ข้อมูลตั้งต้นลง Firebase (สำหรับ Admin)
async function seedFirebase() {
    if (!confirm("คุณต้องการซิงค์ข้อมูลจาก data.json ไปยัง Firebase ใช่หรือไม่?")) return;
    
    try {
        const res = await fetch('/api/seed', { method: 'POST' });
        const data = await res.json();
        alert(data.message || "การซิงค์เสร็จสิ้น");
    } catch (err) {
        alert("ไม่สามารถซิงค์ข้อมูลได้");
    }
}