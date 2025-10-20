import fitz  # PyMuPDF
import os

def list_texts_in_pdf(pdf_path):
    if not os.path.exists(pdf_path):
        print(f"❌ File not found: {pdf_path}")
        return

    doc = fitz.open(pdf_path)
    print(f"🔍 Checking text placeholders in: {pdf_path}")
    print("=" * 60)

    for page_num, page in enumerate(doc, start=1):
        print(f"\n📄 Page {page_num}:")
        text = page.get_text("text")
        lines = text.split("\n")
        for line in lines:
            if "{{" in line and "}}" in line:
                print(f"  ➜ Found placeholder: {line.strip()}")
    doc.close()
    print("\n✅ Scan complete.")

if __name__ == "__main__":
    template_path = "template.pdf"  # make sure this file is in your repo
    list_texts_in_pdf(template_path)
