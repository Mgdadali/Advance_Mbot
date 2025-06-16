import os
import json
from flask import Flask, request
import gspread
from google.oauth2.service_account import Credentials
from datetime import datetime

app = Flask(__name__)

SHEET_ID = '10-gDKaxRQfJqkIoiF3BYQ0YiNXzG7Ml9Pm5r9X9xfCM'
scopes = ["https://www.googleapis.com/auth/spreadsheets"]

# تحميل بيانات اعتماد Google من متغير البيئة
json_creds = os.getenv('GOOGLE_CREDENTIALS')
print("✅ Length of GOOGLE_CREDENTIALS:", len(json_creds) if json_creds else "❌ Not Found")

# تحويل النص إلى dict
info = json.loads(json_creds)
credentials = Credentials.from_service_account_info(info, scopes=scopes)
client = gspread.authorize(credentials)

# فتح Google Sheet وورقة العمل
sheet = client.open_by_key(SHEET_ID).worksheet("sheet")  # عدّل اسم الورقة هنا لو مختلف

# أرقام الموظفين
EMPLOYEES = [
    "201029664170", "201029773000", "201029772000",
    "201055855040", "201029455000", "201027480870", "201055855030"
]

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

def save_client(phone, message):
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    assigned_to = assign_employee()
    sheet.append_row([phone, assigned_to, message, now])
    return assigned_to

@app.route('/webhook', methods=['POST'])
def webhook():
    data = request.json
    if not data or 'data' not in data:
        return "Invalid Data", 400

    message = data['data']
    sender = message.get('from')
    msg_body = message.get('body', '')
    is_group = '@g.us' in sender
    from_me = message.get('fromMe', False)

    if is_group or from_me:
        return "Ignored", 200

    if is_existing_client(sender):
        return "Already assigned", 200

    save_client(sender, msg_body)
    return "Logged", 200

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)
