# Network Programmability Demo (mock RESTCONF, single Fedora box)

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

## 3) mapping กับ script ของคุณ

| Act | ใช้ไฟล์ไหน | ทำอะไรบนจอ |
|---|---|---|
| I — CLI ราชินี | `cli.py` | พิมพ์คำสั่งทีละบรรทัดใน Terminal 2 ให้คนดูเห็นว่ามันช้า/ทีละตัว |
| VI — Python คุยกับ Router | `demo_client.py get` | โชว์ `GET /restconf/...` ได้ JSON กลับมาจริง ไม่ต้องพิมพ์ CLI |
| VI (ต่อ) — ยืนยันว่า state เดียวกัน | สลับ Terminal 2/3 | ตั้งค่าจาก CLI แล้วอ่านค่าจาก `demo_client.py get` ให้เห็นว่าตรงกัน — นี่คือ "จุดขาย" ของ demo |
| VII — พังตรงจังหวะ | `python demo_client.py disable g0/1` แล้ว `python demo_client.py down` | interface โดน shutdown จาก "คนอื่น" แล้วเครื่องก็ "ตาย" (503/timeout) พร้อมกัน — ดูเหมือนของจริงพัง |
| Troubleshooting | `cli.py` → `show ip interface brief` | จะเห็น g0/1 เป็น `administratively down` ทันที (เพราะ shared state) แม้ตอนนั้น RESTCONF จะ unreachable อยู่ (`down` flag) — เดินเรื่องได้ว่า "เข้าไม่ได้ทาง API แต่ CLI local ยังบอกอาการได้" หรือจะสั่ง `up` ก่อนค่อย demo troubleshoot ก็ได้ แล้วแต่จังหวะที่อยากเล่า |
| VII — แก้จบ | `cli.py` → `no shutdown` หรือ `demo_client.py enable g0/1` | โชว์ `200 OK` ปิดท้าย |

หมายเหตุ: `demo_client.py down` / `up` ไม่ใช่ RESTCONF จริง มันคือ "รีโมตของผู้กำกับ" ที่สั่งให้ทุก `/restconf/*` timeout ชั่วคราว ใช้เพื่อคุมจังหวะ ACT VII ให้พังตรงเวลาที่ต้องการ ไม่ต้องพึ่ง error ที่เกิดขึ้นเอง

## 4) เช็คก่อนขึ้นจอจริง

- รัน dry-run เต็มรอบอย่างน้อย 1 ครั้งก่อน present จริง (โดยเฉพาะจังหวะ `down`/`up` ให้จับเวลาว่าเข้ากับบทพูดพอดี)
- ถ้าจะสลับ terminal บนจอ ให้ตั้งชื่อ terminal/tab ไว้ล่วงหน้า (เช่น "CLI", "RESTCONF client", "server log") กันงงตอน live
- server.py ใช้ `--reload` ได้ตอนพัฒนา แต่ตอน present จริงให้รันแบบไม่มี `--reload` (เอาออกจากคำสั่ง) เพื่อกัน auto-restart ไปโดนจังหวะ demo
- ถ้าพอร์ต 8080 ชนกับโปรแกรมอื่นบนเครื่อง ให้เปลี่ยนเลขพอร์ตในคำสั่ง `uvicorn` แล้วแก้ตัวแปร `BASE` ใน `cli.py` และ `demo_client.py` ให้ตรงกัน
- ทุกอย่างผูกกับ `127.0.0.1` (localhost) เท่านั้น ไม่ต้องยุ่งกับ firewall ของ Fedora เลย เพราะไม่มี traffic ข้ามเครื่อง
