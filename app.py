# app.py
import gspread
from google.oauth2.service_account import Credentials
from flask import Flask, request, send_file, render_template_string
import fitz  # PyMuPDF
#import qrcode
import io
import os
import datetime
import random
import json

# Google Sheets setup
import os, json, gspread
from google.oauth2.service_account import Credentials

# Google Sheets setup (use JSON from Render env variable)
SCOPES = ["https://www.googleapis.com/auth/spreadsheets"]

creds_json = json.loads(os.getenv("GOOGLE_CREDS_JSON"))
credentials = Credentials.from_service_account_info(creds_json, scopes=SCOPES)
gc = gspread.authorize(credentials)

# Your Sheet ID (replace with your actual sheet id)
SHEET_ID = "1nMlh5maJD6Xz80hQTmKrUL28R3H2zKsunGzB0Jo2odw"
sheet = gc.open_by_key(SHEET_ID).sheet1

# Path for storing used ticket numbers
USED_NUMBERS_FILE = "used_ticket_numbers.json"

def generate_unique_ticket_number():
    """Generate a unique 6-digit ticket number with GWS prefix."""
    used = set()
    if os.path.exists(USED_NUMBERS_FILE):
        with open(USED_NUMBERS_FILE, "r") as f:
            try:
                used = set(json.load(f))
            except json.JSONDecodeError:
                used = set()

    while True:
        random_number = random.randint(100000, 999999)
        ticket_no = f"GWS-{random_number}"
        if ticket_no not in used:
            used.add(ticket_no)
            break

    with open(USED_NUMBERS_FILE, "w") as f:
        json.dump(list(used), f)

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
    Time: <input name="time" required><br><br>
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
    "{{DATE}}": "date_str",
    "{{TIME}}": "current_time"
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
    #qr_data = f"Goodwillstores@{fullname} - {ticket_no}"
    #qr_img = qrcode.make(qr_data)
    #qr_bytes = io.BytesIO()
    #qr_img.save(qr_bytes, format="PNG")
    #qr_bytes.seek(0)

    template_path = "template.pdf"
    output_path = os.path.join(OUTPUT_DIR, f"{ticket_no}.pdf")

    if not os.path.exists(template_path):
        return "Error: template.pdf not found!", 500

    doc = fitz.open(template_path)
    page = doc[0]

    # === Smart dynamic placeholder replacement (auto-fit & flexible rect, fixed for PyMuPDF 1.24+) ===
    for placeholder, value in replacements.items():
        matches = page.search_for(placeholder)

        if not matches:
            alt_placeholder = placeholder.replace("-", "").replace(" ", "")
            matches = page.search_for(alt_placeholder)

        if not matches:
            print(f"⚠️ Placeholder not found visually: {placeholder}")
            y_offset = 150 + list(replacements.keys()).index(placeholder) * 25
            page.insert_text((80, y_offset), f"{placeholder}: {value}",
                         fontsize=12, fontname="helv", color=(0, 0, 0))
            continue

        for rect in matches:
            text_str = str(value)
            fontname = "helv"
            fontsize = 12

            # measure text width using fitz global function
            text_width = fitz.get_text_length(text_str, fontname=fontname, fontsize=fontsize)
            min_width = rect.width
            new_width = max(min_width, text_width + 6)  # extend rect if text is longer

            # build a new rectangle that grows/shrinks based on text width
            flex_rect = fitz.Rect(rect.x0, rect.y0, rect.x0 + new_width, rect.y1)

            # clear that region
            page.draw_rect(flex_rect, color=(1, 1, 1), fill=(1, 1, 1))

            # adjust font size if text taller than box height
            while fontsize > 6 and fitz.get_text_length(text_str, fontname=fontname, fontsize=fontsize) > flex_rect.width - 2:
                fontsize -= 0.5

            # vertical centering
            y_position = flex_rect.y1 - ((flex_rect.height - fontsize) / 2)

            # insert text inside flexible box
            page.insert_text((flex_rect.x0 + 2, y_position), text_str,
                             fontsize=fontsize, fontname=fontname, color=(0, 0, 0))

    print("✅ All placeholders replaced with dynamic flexible rectangles.")



#Insert QR Code (adjust position as needed)
    #qr_rect = fitz.Rect(430, 120, 520, 210)
    #page.insert_image(qr_rect, stream=qr_bytes)

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

import fitz  # PyMuPDF
import os

def list_texts_in_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return
    doc = fitz.open(pdf_path)
    print(f"\n🔍 Checking text placeholders in: {pdf_path}")
    print("=" * 60)
    for page_num, page in enumerate(doc, start=1):
        print(f"\n📄 Page {page_num}:")
        text = page.get_text("text")
        lines = text.split("\n")
        for line in lines:
            if "{{" in line and "}}" in line:
                print(f"➕ Found placeholder: {line.strip()}")
    doc.close()
    print("\n✅ Scan complete.\n")

# ✅ Run placeholder scan before starting Flask
if os.path.exists("template.pdf"):
    print("\n==============================")
    print("🔍 Scanning template placeholders...")
    print("==============================\n")
    list_texts_in_pdf("template.pdf")
else:
    print("⚠️ template.pdf not found for scan.\n")

# ✅ Then import Flask app and run
from app import app

#if __name__ == "__main__":
 #   app.run(host="0.0.0.0", port=5000)

if __name__ == "__main__":
    import os
    port = int(os.environ.get("PORT", 10000))
    app.run(host="0.0.0.0", port=port)
