# app.py
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request, send_file, render_template_string
import fitz  # PyMuPDF
import qrcode
import io
import os
import datetime
import random
import json

# Google Sheets setup
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]
import json

# Load Google service account from Render environment variable
service_account_info = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
credentials = Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
gc = gspread.authorize(credentials)

# Your Sheet ID
SHEET_ID = "PASTE_YOUR_SHEET_ID_HERE"
sheet = gc.open_by_key(SHEET_ID).sheet1

USED_NUMBERS_FILE = "used_ticket_numbers.json"

def generate_unique_ticket_number():
    """Generate a unique 6-digit ticket number with GWS prefix."""
    if os.path.exists(USED_NUMBERS_FILE):
        with open(USED_NUMBERS_FILE, "r") as f:
            used_numbers = set(json.load(f))
    else:
        used_numbers = set()

    while True:
        random_number = random.randint(100000, 999999)
        ticket_no = f"GWS-{random_number}"
        if ticket_no not in used_numbers:
            used_numbers.add(ticket_no)
            with open(USED_NUMBERS_FILE, "w") as f:
                json.dump(list(used_numbers), f)
            return ticket_no

app = Flask(__name__)

OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

TICKET_FILE = "used_tickets.json"

HTML_FORM = """
<!doctype html>
<html>
<head><title>Goodwillstores Lucrative Raffle</title></head>
<body style="font-family:Arial; margin:40px;">
  <h2>🎟️ Goodwillstores Lucrative Raffle Generator</h2>
  <form method="post">
    Full name: <input name="fullname" required><br><br>
    Ticket price: <input name="price" required><br><br>
    Event place: <input name="place" required><br><br>
    Event date: <input name="date" required><br><br>
    <button type="submit">Generate Ticket</button>
  </form>
</body></html>
"""

# Define placeholders expected in your template
PLACEHOLDERS = {
    "{{NAME}}": "fullname",
    "{{TICKET-NO}}": "ticket_no",
    "{{TICKET_PRICE}}": "price",
    "{{EVENT_PLACE}}": "place",
    "{{DATE}}": "date",
    "{{TIME}}": "time"
}

def generate_unique_ticket():
    """Generate a unique 6-digit ticket number that never repeats."""
    used = set()
    if os.path.exists(TICKET_FILE):
        with open(TICKET_FILE, "r") as f:
            try:
                used = set(json.load(f))
            except json.JSONDecodeError:
                used = set()

    while True:
        rand_num = random.randint(100000, 999999)
        ticket_id = f"GWS-{rand_num}"
        if ticket_id not in used:
            used.add(ticket_id)
            break

    with open(TICKET_FILE, "w") as f:
        json.dump(list(used), f)

    return ticket_id


def fit_font_size(page, rect, text, fontname="helv", max_fontsize=12):
    font = fitz.Font(fontname=fontname)
    for size in range(max_fontsize, 1, -1):
        text_width = font.text_length(text, fontsize=size)
        if text_width <= rect.width:
            return size
    return 8


@app.route("/", methods=["GET", "POST"])
def generate_ticket():
    if request.method == "GET":
        return render_template_string(HTML_FORM)

    fullname = request.form["fullname"]
    price = request.form["price"]
    place = request.form["place"]
    date_str = request.form["date"]
    ticket_no = generate_unique_ticket_number()
    current_time = datetime.datetime.now().strftime("%I:%M %p")

    replacements = {
        "{{NAME}}": fullname,
        "{{TICKET-NO}}": ticket_no,
        "{{TICKET_PRICE}}": price,
        "{{EVENT_PLACE}}": place,
        "{{DATE}}": date_str,
        "{{TIME}}": current_time
    }

    # Generate QR code
    qr_data = f"Goodwillstores@{fullname} - {ticket_no}"
    qr_img = qrcode.make(qr_data)
    qr_bytes = io.BytesIO()
    qr_img.save(qr_bytes, format="PNG")
    qr_bytes.seek(0)

    template_path = "template.pdf"
    output_path = os.path.join(OUTPUT_DIR, f"{ticket_no}.pdf")

    if not os.path.exists(template_path):
        return "Error: template.pdf not found!", 500

    doc = fitz.open(template_path)
    page = doc[0]

    # Find all placeholder rectangles
    placeholder_rects = {}
    for placeholder in replacements.keys():
        rects = page.search_for(placeholder)
        if rects:
            placeholder_rects[placeholder] = rects

    # Cover placeholder text with white boxes
    for placeholder, rects in placeholder_rects.items():
        for r in rects:
            page.draw_rect(r, color=(1, 1, 1), fill=(1, 1, 1))

    # Insert replacement text in the same locations
    for placeholder, rects in placeholder_rects.items():
        text_value = replacements.get(placeholder, "")
        for r in rects:
            fontsize = fit_font_size(page, r, text_value, fontname="helv", max_fontsize=int(r.height * 1.5))
            x = r.x0 + 1
            y = r.y1 - (r.height * 0.15)
            page.insert_text((x, y), text_value, fontsize=fontsize, fontname="helv", color=(0, 0, 0))


    # Insert QR Code (adjust position as needed)
        qr_rect = fitz.Rect(430, 120, 520, 210)
        page.insert_image(qr_rect, stream=qr_bytes)

        doc.save(output_path)
        doc.close()

    # Log data to Google Sheet
        sheet.append_row([
            fullname,
            ticket_no,
            price,
            place,
            date_str,
            current_time
        ])

        return send_file(output_path, as_attachment=True)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
