import os
import json
from flask import Flask, request
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime
import requests

app = Flask(__name__)

# إعداد Google Sheet
SHEET_ID = '10-gDKaxRQfJqkIoiF3BYQ0YiNXzG7Ml9Pm5r9X9xfCM'
scopes = ["https://www.googleapis.com/auth/spreadsheets"]

# تحميل بيانات اعتماد Google من متغير البيئة
json_creds = os.getenv('GOOGLE_CREDENTIALS')
print("✅ تم العثور على GOOGLE_CREDENTIALS بطول:", len(json_creds) if json_creds else "❌ لم يتم العثور على GOOGLE_CREDENTIALS")

# تحويل النص إلى dict
info = json.loads(json_creds)
credentials = Credentials.from_service_account_info(info, scopes=scopes)
client = gspread.authorize(credentials)

# فتح Google Sheet واختبار الوصول
try:
    sheet = client.open_by_key(SHEET_ID).worksheet("sheet")
    print("✅ تم فتح الشيت بنجاح:", sheet.title)
except Exception as e:
    print("❌ فشل في فتح الشيت:", str(e))
    raise e

# قائمة الموظفين
EMPLOYEES = [
    "201029664170", "201029773000", "201029772000",
    "201055855040", "201029455000", "201027480870", "201055855030"
]

ULTRAMSG_TOKEN = os.getenv('ULTRAMSG_TOKEN')
ULTRAMSG_INSTANCE = os.getenv('ULTRAMSG_INSTANCE')


def assign_employee():
    data = sheet.get_all_records()
    assigned_counts = {emp: 0 for emp in EMPLOYEES}
    for row in data:
        emp = row.get("AssignedTo")
        if emp in assigned_counts:
            assigned_counts[emp] += 1
    return min(assigned_counts, key=assigned_counts.get)


def is_existing_client(phone):
    records = sheet.get_all_records()
    return any(row['Phone'] == phone for row in records)


def update_last_message(phone, message):
    all_data = sheet.get_all_records()
    for idx, row in enumerate(all_data, start=2):  # الصف 2 لأن الصف 1 يحتوي على العناوين
        if row['Phone'] == phone:
            sheet.update_cell(idx, 3, message)  # تحديث LastMessage
            sheet.update_cell(idx, 4, datetime.now().strftime('%Y-%m-%d %H:%M:%S'))  # تحديث الوقت
            print("🔄 تم تحديث آخر رسالة للعميل")
            break


def save_client(phone, message):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    assigned_to = assign_employee()
    sheet.append_row([phone, assigned_to, message, now])
    send_welcome_message(phone)
    return assigned_to


def send_welcome_message(phone):
    if "@c.us" in phone:
        phone = phone.replace("@c.us", "")
    if not phone.startswith("2"):
        print("❌ الرقم غير صالح للإرسال:", phone)
        return

    url = f"https://api.ultramsg.com/{ULTRAMSG_INSTANCE}/messages/chat"
    headers = {"Content-Type": "application/x-www-form-urlencoded"}
    payload = {
        "token": ULTRAMSG_TOKEN,
        "to": phone,
        "body": "مرحبًا بك! تم استلام رسالتك وسنقوم بالرد عليك قريبًا."
    }
    try:
        response = requests.post(url, headers=headers, data=payload)
        print("📤 رسالة الترحيب - تم الإرسال:", response.status_code, response.text)
    except Exception as e:
        print("❌ فشل إرسال رسالة الترحيب:", e)


@app.route('/webhook', methods=['POST'])
def webhook():
    try:
        data = request.get_json(force=True)
        print("📥 تم استلام الطلب:", json.dumps(data, indent=2))

        if not data or 'data' not in data:
            print("❌ البيانات المستلمة غير صالحة: الحقل 'data' مفقود")
            return "Invalid Data", 400

        message = data['data']
        print("📦 محتوى الرسالة:", message)

        sender = message.get('from')
        msg_body = message.get('body', '')
        is_group = '@g.us' in sender if sender else False
        from_me = message.get('fromMe', False)

        print(f"📞 الرقم: {sender}, المحتوى: {msg_body}, من مجموعة: {is_group}, منّي: {from_me}")

        if is_group or from_me:
            return "Ignored", 200

        if is_existing_client(sender):
            update_last_message(sender, msg_body)
            print("🔁 العميل موجود مسبقًا - تم تحديث الرسالة")
            return "Already assigned", 200

        assigned_to = save_client(sender, msg_body)
        print(f"✅ تم تخصيص العميل إلى: {assigned_to}")
        return "Logged", 200

    except Exception as e:
        print("💥 خطأ أثناء المعالجة:", str(e))
        return "Error", 500


if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
