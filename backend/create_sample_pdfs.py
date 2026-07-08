import os
from reportlab.lib.pagesizes import letter
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

def create_pdf(filename: str, title: str, sections: list):
    """
    Creates a simple styled PDF document.
    """
    os.makedirs(os.path.dirname(filename), exist_ok=True)
    doc = SimpleDocTemplate(filename, pagesize=letter,
                            rightMargin=54, leftMargin=54,
                            topMargin=54, bottomMargin=54)
    
    styles = getSampleStyleSheet()
    
    # Custom Styles
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        spaceAfter=20,
        textColor='#1e293b'
    )
    
    heading_style = ParagraphStyle(
        'DocHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        spaceBefore=12,
        spaceAfter=6,
        textColor='#4f46e5'
    )
    
    body_style = ParagraphStyle(
        'DocBody',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        spaceAfter=10,
        textColor='#334155'
    )
    
    story = []
    
    # Add Title
    story.append(Paragraph(title, title_style))
    story.append(Spacer(1, 12))
    
    # Add Sections
    for heading, text in sections:
        story.append(Paragraph(heading, heading_style))
        story.append(Paragraph(text, body_style))
        story.append(Spacer(1, 10))
        
    doc.build(story)
    print(f"Created PDF: {filename}")

if __name__ == "__main__":
    current_dir = os.path.dirname(os.path.abspath(__file__))
    sample_dir = os.path.join(current_dir, "..", "data", "samples")
    
    # 1. Tender Requirements PDF
    tender_file = os.path.join(sample_dir, "ongc_tender_pipeline.pdf")
    tender_title = "ONGC Tender Specifications: Pipeline Installation Project"
    tender_sections = [
        ("Section 1: Pipeline Material Specifications", 
         "All line pipes supplied under this tender must strictly conform to API 5L Grade X70 specifications. "
         "The pipeline must be designed to sustain a maximum operating pressure of 100 bar. "
         "The pipe wall thickness must be at least 15.8mm to withstand corrosion and high pressure under seabed conditions."),
        
        ("Section 2: Quality and Safety Certifications",
         "The pipe manufacturer must hold a valid API Spec Q1 and ISO 9001 certification. "
         "All certifications must remain valid throughout the entire duration of the contract. "
         "Proof of certification must be submitted in the technical bid package."),
        
        ("Section 3: Delivery Terms and Warranty",
         "All materials must be delivered to the designated ONGC warehouse within 6 months of contract signing. "
         "The supplied piping and equipment must be warranted for 18 months from the date of delivery or 12 months "
         "from the date of commissioning, whichever is earlier."),
        
        ("Section 4: Hydrostatic Testing Requirements",
         "Pipes must undergo a hydrostatic pressure test at 1.5 times the maximum operating pressure, which translates "
         "to a testing pressure of 150 bar. The test pressure must be held continuously for a minimum of 24 hours. "
         "A chart recording the pressure over the entire 24-hour test period must be submitted as compliance record.")
    ]
    create_pdf(tender_file, tender_title, tender_sections)
    
    # 2. Vendor Technical Proposal PDF
    proposal_file = os.path.join(sample_dir, "vendor_bid_proposal.pdf")
    proposal_title = "Technical Bid Proposal: High-Pressure Pipeline Supply"
    proposal_sections = [
        ("Section 1: Executive Summary & Corporate Experience",
         "We are pleased to submit our technical bid for the ONGC Pipeline Installation project. "
         "Our company has over 15 years of experience supplying heavy industries in oil and gas sector. "
         "We possess advanced manufacturing facilities located in Mumbai."),
        
        ("Section 2: Proposed Pipe Material Specifications",
         "We propose supplying line pipes made of high-quality carbon steel conforming to API 5L Grade X65 specs. "
         "Our carbon steel piping is rated for up to 90 bar maximum operating pressure, which has been proven in "
         "several regional shallow water projects. The wall thickness proposed is 16.0mm, exceeding corrosion margins."),
        
        ("Section 3: Quality Management Certificates",
         "Our manufacturing plant operates under a strict Quality Management System. We hold active ISO 9001 and "
         "ISO 14001 environmental certificates. While we do not hold the API Spec Q1 certificate currently, we comply "
         "fully with all its guidelines in our processes."),
        
        ("Section 4: Supply Logistics and Warranty Period",
         "We guarantee delivery of all ordered piping materials within 5 months of receiving the signed contract, "
         "which is ahead of schedule. We offer a comprehensive product warranty for 18 months from the date of delivery "
         "to cover any manufacturing flaws."),
        
        ("Section 5: Testing and Inspection Protocols",
         "Our quality inspection includes hydrostatic pressure tests on all supplied pipes. "
         "We conduct hydrostatic tests at 150 bar pressure. The pressure test is held for a duration of 12 hours "
         "using automated pressure gauges, and logs will be provided with shipment.")
    ]
    create_pdf(proposal_file, proposal_title, proposal_sections)
