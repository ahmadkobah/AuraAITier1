"""Create test invoice with signature for AI testing"""
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
import os

def draw_handwritten_signature(c, x, y):
    """Draw handwritten-style signature using bezier curves"""
    c.saveState()
    c.setStrokeColor(colors.HexColor('#1a237e'))
    c.setLineWidth(2.0)
    c.setLineCap(1)
    c.setLineJoin(1)
    
    # J curve
    path = c.beginPath()
    path.moveTo(x, y)
    path.curveTo(x+5, y+20, x+15, y+25, x+20, y+15)
    path.curveTo(x+25, y+5, x+20, y-5, x+25, y-8)
    c.drawPath(path, stroke=1, fill=0)
    
    # ohn
    path = c.beginPath()
    path.moveTo(x+30, y)
    path.curveTo(x+35, y+10, x+45, y+12, x+55, y+8)
    path.curveTo(x+65, y+4, x+70, y+10, x+80, y+6)
    c.drawPath(path, stroke=1, fill=0)
    
    # S
    path = c.beginPath()
    path.moveTo(x+95, y+15)
    path.curveTo(x+90, y+20, x+85, y+15, x+88, y+8)
    path.curveTo(x+92, y+2, x+100, y-2, x+95, y-8)
    c.drawPath(path, stroke=1, fill=0)
    
    # mith + flourish
    path = c.beginPath()
    path.moveTo(x+98, y)
    path.curveTo(x+105, y+8, x+115, y+10, x+125, y+6)
    path.curveTo(x+135, y+2, x+145, y+8, x+155, y+4)
    path.curveTo(x+165, y, x+175, y+5, x+180, y)
    path.curveTo(x+185, y-5, x+150, y-15, x+100, y-12)
    c.drawPath(path, stroke=1, fill=0)
    
    c.restoreState()

def create_test_invoice():
    output_path = os.path.join(os.path.dirname(__file__), "test_invoice_with_signature.pdf")
    c = canvas.Canvas(output_path, pagesize=letter)
    width, height = letter
    
    # Header
    c.setFont("Helvetica-Bold", 24)
    c.setFillColor(colors.darkblue)
    c.drawString(50, height - 50, "ACME Corporation")
    
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawString(50, height - 65, "123 Business Street, New York, NY 10001")
    c.drawString(50, height - 77, "Phone: (555) 123-4567 | billing@acmecorp.com")
    
    c.setFont("Helvetica-Bold", 28)
    c.setFillColor(colors.darkblue)
    c.drawRightString(width - 50, height - 50, "INVOICE")
    
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawRightString(width - 150, height - 80, "INV-2024-001234")
    c.drawRightString(width - 150, height - 95, "December 9, 2025")
    
    c.setStrokeColor(colors.darkblue)
    c.setLineWidth(2)
    c.line(50, height - 110, width - 50, height - 110)
    
    # Bill To
    y = height - 140
    c.setFont("Helvetica-Bold", 10)
    c.drawString(50, y, "Bill To:")
    c.setFont("Helvetica", 10)
    c.drawString(50, y - 15, "TechStart Solutions Inc.")
    c.drawString(50, y - 27, "John Smith")
    c.drawString(50, y - 39, "456 Innovation Drive, San Francisco, CA")
    
    # Table with borders
    y = height - 220
    
    # Table header
    c.setFillColor(colors.darkblue)
    c.rect(50, y, width - 100, 20, fill=True, stroke=True)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 9)
    c.drawString(55, y + 5, "Qty")
    c.drawString(85, y + 5, "Description")
    c.drawString(340, y + 5, "Unit Price")
    c.drawString(420, y + 5, "Tax")
    c.drawString(480, y + 5, "Amount")
    
    # Table rows
    items = [
        ("5", "Professional Software License", "$299.00", "8%", "$1,495.00"),
        ("10", "Cloud Storage (1TB/year)", "$49.99", "8%", "$499.90"),
        ("3", "Technical Support Premium", "$199.00", "0%", "$597.00"),
        ("1", "Training Services", "$1,500.00", "8%", "$1,500.00"),
        ("25", "User Access Tokens", "$15.00", "8%", "$375.00"),
    ]
    
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    for i, (qty, desc, price, tax, amt) in enumerate(items):
        row_y = y - 20 - (i * 18)
        # Row border
        c.setStrokeColor(colors.lightgrey)
        c.rect(50, row_y - 3, width - 100, 18, stroke=True, fill=False)
        # Content
        c.drawString(55, row_y + 2, qty)
        c.drawString(85, row_y + 2, desc)
        c.drawRightString(400, row_y + 2, price)
        c.drawRightString(450, row_y + 2, tax)
        c.drawRightString(545, row_y + 2, amt)
    
    # Totals
    y = height - 360
    c.setFont("Helvetica", 10)
    c.drawRightString(470, y, "Subtotal: $4,466.90")
    c.drawRightString(470, y - 15, "Tax: $311.75")
    c.setFont("Helvetica-Bold", 11)
    c.setFillColor(colors.darkblue)
    c.drawRightString(470, y - 35, "TOTAL: $4,803.65")
    
    # Signature boxes
    y = height - 480
    
    # Box 1
    c.setStrokeColor(colors.grey)
    c.setLineWidth(0.5)
    c.rect(50, y - 100, 200, 100, stroke=True)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawString(55, y - 10, "Authorized Signature")
    draw_handwritten_signature(c, 60, y - 50)
    c.setStrokeColor(colors.black)
    c.line(55, y - 70, 240, y - 70)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(55, y - 82, "Michael Thompson, CFO")
    c.drawString(55, y - 94, "Date: December 9, 2025")
    
    # Box 2
    c.setStrokeColor(colors.grey)
    c.rect(300, y - 100, 200, 100, stroke=True)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.grey)
    c.drawString(305, y - 10, "Customer Signature")
    draw_handwritten_signature(c, 310, y - 50)
    c.setStrokeColor(colors.black)
    c.line(305, y - 70, 490, y - 70)
    c.setFillColor(colors.black)
    c.setFont("Helvetica", 9)
    c.drawString(305, y - 82, "John Smith, Procurement")
    c.drawString(305, y - 94, "Date: December 9, 2025")
    
    c.save()
    print(f"Created: {output_path}")
    return output_path

if __name__ == "__main__":
    create_test_invoice()
