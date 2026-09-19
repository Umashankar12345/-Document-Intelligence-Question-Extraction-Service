import os
from pathlib import Path
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image, ImageDraw, ImageFont, ImageFilter


def generate_all_samples():
    out_dir = Path(__file__).resolve().parent.parent / "samples"
    out_dir.mkdir(parents=True, exist_ok=True)

    # 1. Generate standard qpaper.pdf
    qpaper_path = out_dir / "qpaper.pdf"
    c = canvas.Canvas(str(qpaper_path), pagesize=letter)
    width, height = letter

    # Page 1
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2.0, height - 50, "Computer Science Department Examination")
    c.setFont("Helvetica", 10)
    c.drawCentredString(width / 2.0, height - 70, "Subject: Operating Systems & Data Structures")
    c.setLineWidth(1)
    c.line(50, height - 80, width - 50, height - 80)

    y = height - 110
    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Section A — Multiple Choice Questions")
    y -= 30

    questions = [
        (
            "1. What is the primary function of an operating system kernel?",
            [
                "(A) Word processing and spreadsheet calculations",
                "(B) Managing hardware resources and process execution",
                "(C) Sending and receiving external network packets only",
                "(D) Compiling web application assets",
            ],
        ),
        (
            "2. Which data structure operates on a Last-In, First-Out (LIFO) discipline?",
            [
                "(A) Queue",
                "(B) Balanced Binary Search Tree",
                "(C) Stack",
                "(D) Circular Buffer",
            ],
        ),
        (
            "3. What is the asymptotic time complexity of searching an element in a balanced BST?",
            [
                "(A) O(n)",
                "(B) O(log n)",
                "(C) O(n log n)",
                "(D) O(1)",
            ],
        ),
    ]

    for q_text, opts in questions:
        c.setFont("Helvetica-Bold", 11)
        c.drawString(50, y, q_text)
        y -= 20
        c.setFont("Helvetica", 10)
        for opt in opts:
            c.drawString(70, y, opt)
            y -= 18
        y -= 15

    c.setFont("Helvetica-Bold", 12)
    c.drawString(50, y, "Section B — Short Answer Questions")
    y -= 25
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "4. Explain the key distinctions between a process and a thread.")
    y -= 35
    c.drawString(50, y, "5. Describe the role of page tables and TLB in virtual memory management.")

    c.showPage()
    c.save()
    print(f"Generated: {qpaper_path}")

    # 2. Generate cross_page_qpaper.pdf
    cross_path = out_dir / "cross_page_qpaper.pdf"
    c = canvas.Canvas(str(cross_path), pagesize=letter)
    
    # Page 1
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, height - 50, "Advanced Networking Examination — Page 1")
    y = height - 90
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "1. What is the default subnet mask for a Class C IPv4 network?")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(70, y, "(A) 255.0.0.0")
    y -= 18
    c.drawString(70, y, "(B) 255.255.0.0")
    y -= 18
    c.drawString(70, y, "(C) 255.255.255.0")
    y -= 18
    c.drawString(70, y, "(D) 255.255.255.255")
    y -= 30

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "2. Which layer of the OSI model does a network router operate at?")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(70, y, "(A) Data Link Layer")
    y -= 18
    c.drawString(70, y, "(B) Network Layer")
    y -= 18
    c.drawString(70, y, "(C) Transport Layer")
    y -= 18
    c.drawString(70, y, "(D) Physical Layer")
    y -= 40

    # Question 3 starts at bottom of Page 1 without its options
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "3. Which transport layer protocol provides reliable, connection-oriented byte stream delivery")
    y -= 18
    c.drawString(50, y, "with flow control and congestion management mechanisms?")
    c.showPage()

    # Page 2: Options for Question 3 continue at top of page, followed by Question 4
    y = height - 50
    c.setFont("Helvetica", 10)
    c.drawString(70, y, "(A) User Datagram Protocol (UDP)")
    y -= 18
    c.drawString(70, y, "(B) Transmission Control Protocol (TCP)")
    y -= 18
    c.drawString(70, y, "(C) Internet Control Message Protocol (ICMP)")
    y -= 18
    c.drawString(70, y, "(D) Address Resolution Protocol (ARP)")
    y -= 35

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "4. What is the standard well-known TCP port number for HTTPS secure traffic?")
    y -= 20
    c.setFont("Helvetica", 10)
    c.drawString(70, y, "(A) 22")
    y -= 18
    c.drawString(70, y, "(B) 80")
    y -= 18
    c.drawString(70, y, "(C) 443")
    y -= 18
    c.drawString(70, y, "(D) 8080")
    c.showPage()
    c.save()
    print(f"Generated: {cross_path}")

    # 3. Generate answer_key.pdf
    ans_path = out_dir / "answer_key.pdf"
    c = canvas.Canvas(str(ans_path), pagesize=letter)
    c.setFont("Helvetica-Bold", 16)
    c.drawCentredString(width / 2.0, height - 50, "Official Examination Answer Key")
    c.line(50, height - 60, width - 50, height - 60)
    y = height - 100
    c.setFont("Helvetica", 12)
    answers = [
        "1. B",
        "2. C",
        "3. B",
        "4. Process has its own address space while threads share address space within a process",
        "5. Page faults occur when virtual page is not in physical RAM",
    ]
    for ans in answers:
        c.drawString(70, y, ans)
        y -= 30
    c.showPage()
    c.save()
    print(f"Generated: {ans_path}")

    # 4. Generate page1.jpg (Clean scanned question image)
    img1_path = out_dir / "page1.jpg"
    img = Image.new("RGB", (800, 1000), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((50, 50), "Mock Test Paper — Physics Section", fill=(0, 0, 0))
    draw.text((50, 100), "1. What is the SI unit of electric resistance?", fill=(0, 0, 0))
    draw.text((80, 130), "(A) Volt", fill=(0, 0, 0))
    draw.text((80, 160), "(B) Ohm", fill=(0, 0, 0))
    draw.text((80, 190), "(C) Ampere", fill=(0, 0, 0))
    draw.text((80, 220), "(D) Watt", fill=(0, 0, 0))
    draw.text((50, 280), "2. What is the acceleration due to gravity on Earth?", fill=(0, 0, 0))
    draw.text((80, 310), "(A) 9.8 m/s^2", fill=(0, 0, 0))
    draw.text((80, 340), "(B) 8.9 m/s^2", fill=(0, 0, 0))
    draw.text((80, 370), "(C) 10.5 m/s^2", fill=(0, 0, 0))
    draw.text((80, 400), "(D) 3.14 m/s^2", fill=(0, 0, 0))
    img.save(img1_path, "JPEG")
    print(f"Generated: {img1_path}")

    # 5. Generate blurry.png (Low-quality scan to test low_ocr / needs_review)
    blurry_path = out_dir / "blurry.png"
    b_img = Image.new("RGB", (600, 800), color=(240, 240, 230))
    b_draw = ImageDraw.Draw(b_img)
    b_draw.text((40, 40), "Faint illegible noisy text scan 123", fill=(215, 215, 215))
    b_draw.text((40, 80), "1. ?? uncertain query ??", fill=(205, 205, 205))
    # Apply severe blur
    b_img = b_img.filter(ImageFilter.GaussianBlur(radius=8))
    b_img.save(blurry_path, "PNG")
    print(f"Generated: {blurry_path}")


if __name__ == "__main__":
    generate_all_samples()
