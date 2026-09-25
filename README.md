# Network Programmability Demo (mock RESTCONF, single Fedora box)
### Presentation Slide Link: "https://canva.link/evh2megedfaoiqv"
```
**เอกสารที่เกี่ยวข้อง**
1. grp8 - Network Programmability
2. Report
3. TopologySimulationLogic
4. Architecture

```
3 ไฟล์, 1 เครื่อง, ไม่ต้องมี IOS/GNS3:

- `server.py` — ตัวปลอม "router" ที่พูด RESTCONF (FastAPI) เก็บ state ในหน่วยความจำ
- `cli.py` — ตัวปลอม Cisco CLI (`enable`, `configure terminal`, `no shutdown`, `show ...`) ที่คุย backend เดียวกับ server.py
- `demo_client.py` — สคริปต์ Python ที่แสดงบทบาท "โปรแกรมคุยกับ router ผ่าน RESTCONF" ใน Act VI/VII
- `gui.py` — หน้าจอ Interactive Pygame Visualizer (CLI + RESTCONF + Router LED Status + Control Buttons)

ทั้ง 3 ตัวแชร์ state เดียวกันผ่าน HTTP → ถ้าสั่ง `no shutdown` จาก CLI แล้วไปเปิด `demo_client.py get` จะเห็น interface up ตรงกันจริง ๆ ไม่ใช่ mock คนละก้อน

## 1) ติดตั้ง (ทำครั้งเดียว)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## 2) เปิด 3 terminal (หรือ 3 tmux pane)

**Terminal 1 — รัน server (เปิดทิ้งไว้ตลอด demo):**
```bash
source venv/bin/activate
uvicorn server:app --host 127.0.0.1 --port 8080
```

**Terminal 2 — CLI (สำหรับ Act I):**
```bash
source venv/bin/activate
python cli.py
```
```
Router> enable
Router# configure terminal
Router(config)# interface g0/0
Router(config-if)# no shutdown
Router(config-if)# end
Router# show ip interface brief
```

**Terminal 3 — Python/RESTCONF client (สำหรับ Act VI/VII):**
```bash
source venv/bin/activate
python demo_client.py get
```
# Enjoy Experimental!