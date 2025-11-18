"""Create a realistic test invoice PDF with actual text content"""
from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from datetime import datetime

def create_test_invoice(filename="test_invoice_realistic.pdf"):
    """Create a test invoice with realistic content"""
    
    doc = SimpleDocTemplate(filename, pagesize=letter)
    story = []
    styles = getSampleStyleSheet()
    
    # Title
    title_style = ParagraphStyle(
        'CustomTitle',
        parent=styles['Heading1'],
        fontSize=24,
        textColor=colors.HexColor('#2C3E50'),
        spaceAfter=30,
    )
    
    story.append(Paragraph("INVOICE", title_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Company info
    company_style = styles['Normal']
    story.append(Paragraph("<b>Acme Corporation</b>", company_style))
    story.append(Paragraph("123 Business Street", company_style))
    story.append(Paragraph("New York, NY 10001", company_style))
    story.append(Paragraph("Phone: (555) 123-4567", company_style))
    story.append(Paragraph("Email: billing@acmecorp.com", company_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Invoice details
    invoice_data = [
        ['Invoice Number:', 'INV-2025-001234'],
        ['Invoice Date:', datetime.now().strftime('%B %d, %Y')],
        ['Due Date:', 'December 17, 2025'],
        ['Customer ID:', 'CUST-789'],
    ]
    
    invoice_table = Table(invoice_data, colWidths=[2*inch, 3*inch])
    invoice_table.setStyle(TableStyle([
        ('FONTNAME', (0, 0), (0, -1), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, -1), 11),
        ('TEXTCOLOR', (0, 0), (0, -1), colors.HexColor('#2C3E50')),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
    ]))
    
    story.append(invoice_table)
    story.append(Spacer(1, 0.4*inch))
    
    # Bill to
    story.append(Paragraph("<b>BILL TO:</b>", company_style))
    story.append(Paragraph("GlobalTech Solutions Inc.", company_style))
    story.append(Paragraph("456 Client Avenue, Suite 200", company_style))
    story.append(Paragraph("San Francisco, CA 94105", company_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Items table
    items_data = [
        ['Item', 'Description', 'Qty', 'Unit Price', 'Total'],
        ['Product A', 'Premium Widget with advanced features', '10', '$150.00', '$1,500.00'],
        ['Product B', 'Standard Service Package', '5', '$200.00', '$1,000.00'],
        ['Product C', 'Consulting Hours', '20', '$125.00', '$2,500.00'],
        ['Product D', 'Software License (Annual)', '1', '$3,500.00', '$3,500.00'],
    ]
    
    items_table = Table(items_data, colWidths=[1.2*inch, 2.5*inch, 0.6*inch, 1*inch, 1*inch])
    items_table.setStyle(TableStyle([
        # Header row
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#34495E')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('FONTNAME', (0, 0), (-1, 0), 'Helvetica-Bold'),
        ('FONTSIZE', (0, 0), (-1, 0), 11),
        ('ALIGN', (2, 0), (-1, -1), 'RIGHT'),
        ('ALIGN', (0, 0), (1, -1), 'LEFT'),
        
        # Data rows
        ('FONTNAME', (0, 1), (-1, -1), 'Helvetica'),
        ('FONTSIZE', (0, 1), (-1, -1), 10),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor('#ECF0F1')]),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('VALIGN', (0, 0), (-1, -1), 'MIDDLE'),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
    ]))
    
    story.append(items_table)
    story.append(Spacer(1, 0.3*inch))
    
    # Totals
    totals_data = [
        ['', '', '', 'Subtotal:', '$8,500.00'],
        ['', '', '', 'Tax (8.5%):', '$722.50'],
        ['', '', '', 'Shipping:', '$125.00'],
        ['', '', '', '<b>TOTAL DUE:</b>', '<b>$9,347.50</b>'],
    ]
    
    totals_table = Table(totals_data, colWidths=[1.2*inch, 2.5*inch, 0.6*inch, 1*inch, 1*inch])
    totals_table.setStyle(TableStyle([
        ('ALIGN', (3, 0), (-1, -1), 'RIGHT'),
        ('FONTNAME', (3, 0), (3, 2), 'Helvetica'),
        ('FONTNAME', (4, 0), (4, 2), 'Helvetica-Bold'),
        ('FONTNAME', (3, 3), (-1, 3), 'Helvetica-Bold'),
        ('FONTSIZE', (3, 3), (-1, 3), 12),
        ('TEXTCOLOR', (3, 3), (-1, 3), colors.HexColor('#E74C3C')),
        ('LINEABOVE', (3, 3), (-1, 3), 2, colors.HexColor('#34495E')),
        ('TOPPADDING', (3, 3), (-1, 3), 10),
    ]))
    
    story.append(totals_table)
    story.append(Spacer(1, 0.5*inch))
    
    # Payment terms
    story.append(Paragraph("<b>Payment Terms:</b>", company_style))
    story.append(Paragraph("Payment is due within 30 days of invoice date.", company_style))
    story.append(Paragraph("Please make checks payable to Acme Corporation.", company_style))
    story.append(Paragraph("Wire transfer details available upon request.", company_style))
    story.append(Spacer(1, 0.3*inch))
    
    # Footer
    footer_style = ParagraphStyle(
        'Footer',
        parent=styles['Normal'],
        fontSize=9,
        textColor=colors.grey,
    )
    story.append(Paragraph("Thank you for your business!", footer_style))
    story.append(Paragraph("For questions about this invoice, please contact billing@acmecorp.com", footer_style))
    
    # Build PDF
    doc.build(story)
    print(f"✓ Created test invoice: {filename}")
    
    # Print file size
    import os
    size = os.path.getsize(filename)
    print(f"  File size: {size:,} bytes")
    print(f"  This is a REAL invoice with actual text content!")

if __name__ == "__main__":
    create_test_invoice()
