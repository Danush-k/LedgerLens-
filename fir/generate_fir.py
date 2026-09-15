"""A realistic FIR for demonstrating document intake.

Run with the backend virtualenv from the project root:

    backend/.venv/bin/python fir/generate_fir.py

Regenerate this rather than editing the PDF by hand - the suspect wallet
appears in two places, and a document whose narrative names one address
while its data section names another is exactly the inconsistency the
extractor would surface at the worst possible moment.


Modelled on the Integrated Form IF1-A used by state police, so the upload
demo exercises the same layout an investigator would actually receive
rather than a tidy synthetic paragraph.
"""
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle,
)

SUSPECT = "1CRLGcaXajtWVF5EopZgQUqE12dKn8Rtuh"
OUT_DIR = Path(__file__).resolve().parent

base = getSampleStyleSheet()
H = ParagraphStyle("H", parent=base["Normal"], fontName="Helvetica-Bold",
                   fontSize=13, leading=16, alignment=TA_CENTER, spaceAfter=2)
SUB = ParagraphStyle("SUB", parent=base["Normal"], fontName="Helvetica",
                     fontSize=9, leading=12, alignment=TA_CENTER,
                     textColor=colors.HexColor("#333333"), spaceAfter=10)
SEC = ParagraphStyle("SEC", parent=base["Normal"], fontName="Helvetica-Bold",
                     fontSize=9.5, leading=13, spaceBefore=9, spaceAfter=4)
BODY = ParagraphStyle("BODY", parent=base["Normal"], fontName="Helvetica",
                      fontSize=9, leading=13.5, alignment=TA_JUSTIFY)
CELL = ParagraphStyle("CELL", parent=base["Normal"], fontName="Helvetica",
                      fontSize=8.5, leading=12)
CELLB = ParagraphStyle("CELLB", parent=CELL, fontName="Helvetica-Bold")

story = []
story.append(Paragraph("FIRST INFORMATION REPORT", H))
story.append(Paragraph(
    "(Under Section 173 Bharatiya Nagarik Suraksha Sanhita, 2023)<br/>"
    "Integrated Form IF1-A &nbsp;·&nbsp; Cyber Crime Police Station, Bengaluru City", SUB))


def grid(rows, widths):
    t = Table(rows, colWidths=widths)
    t.setStyle(TableStyle([
        ("GRID", (0, 0), (-1, -1), 0.6, colors.HexColor("#888888")),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f0f0")),
        ("LEFTPADDING", (0, 0), (-1, -1), 5),
        ("RIGHTPADDING", (0, 0), (-1, -1), 5),
        ("TOPPADDING", (0, 0), (-1, -1), 4),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
    ]))
    return t


def kv(rows):
    return grid([[Paragraph(k, CELLB), Paragraph(v, CELL)] for k, v in rows],
                [5.2 * cm, 11.6 * cm])


story.append(Paragraph("1. DISTRICT / POLICE STATION / FIR PARTICULARS", SEC))
story.append(kv([
    ("District", "Bengaluru City"),
    ("Police Station", "Cyber Crime Police Station, C.I.D. Annexe"),
    ("FIR No.", "0147/2026"),
    ("Date &amp; Time of FIR", "04/09/2026 at 11:20 hrs"),
    ("NCRP Acknowledgement No.", "NCRP/2026/KA/0004471"),
]))

story.append(Paragraph("2. ACTS AND SECTIONS", SEC))
story.append(kv([
    ("Bharatiya Nyaya Sanhita, 2023", "Sections 318(4) (cheating), 319(2) (cheating by personation)"),
    ("Information Technology Act, 2000", "Sections 66C (identity theft), 66D (cheating by personation using computer resource)"),
]))

story.append(Paragraph("3. COMPLAINANT / INFORMANT", SEC))
story.append(kv([
    ("Name", "Ramesh Kumar Iyer"),
    ("Father's / Husband's Name", "Sri. Subramanian Iyer"),
    ("Age / Occupation", "41 years / Software Engineer"),
    ("Address", "No. 214, 3rd Cross, HSR Layout Sector 2, Bengaluru - 560102"),
    ("Mobile / Email", "+91 98450 xxxxx / rk.iyer@example.com"),
]))

story.append(Paragraph("4. PARTICULARS OF THE OFFENCE", SEC))
story.append(kv([
    ("Date / Period of Offence", "12/08/2026 to 29/08/2026"),
    ("Place of Occurrence", "Online / Cyberspace (transactions initiated from complainant's residence)"),
    ("Total Amount Defrauded", "Rs. 47,50,000/- (Rupees Forty Seven Lakh Fifty Thousand only)"),
    ("Mode of Payment", "Bank transfer to peer-to-peer exchange, converted to Bitcoin (BTC)"),
]))

story.append(Paragraph("5. SUSPECT / DIGITAL ASSET DETAILS", SEC))
story.append(kv([
    ("Suspect Wallet Address (BTC)", f"<font face='Courier'>{SUSPECT}</font>"),
    ("Blockchain Network", "Bitcoin (BTC) mainnet"),
    ("Suspect Platform", "\"AlphaQuant Capital\" - www.alphaquant-invest[.]com (now offline)"),
    ("Suspect Contact", "WhatsApp +91 76xxx xxxxx, Telegram @alphaquant_advisor"),
    ("Beneficiary Bank (first leg)", "A/c 50xxxxxxxx1183, IFSC UTIB000xxxx"),
]))

story.append(Paragraph("6. SCHEDULE OF DISPUTED TRANSACTIONS", SEC))
tx_rows = [[Paragraph(c, CELLB) for c in
            ("Sl.", "Date", "Amount (Rs.)", "Bank / Mode", "Destination")]]
for sl, date, amt, mode, dest in [
    ("1", "12/08/2026", "2,50,000", "HDFC IMPS", "P2P vendor - WazirX"),
    ("2", "14/08/2026", "5,00,000", "HDFC NEFT", "P2P vendor - WazirX"),
    ("3", "17/08/2026", "7,50,000", "ICICI RTGS", "P2P vendor - CoinDCX"),
    ("4", "20/08/2026", "10,00,000", "ICICI RTGS", "P2P vendor - CoinDCX"),
    ("5", "23/08/2026", "8,00,000", "HDFC RTGS", "Direct BTC purchase"),
    ("6", "26/08/2026", "9,50,000", "HDFC RTGS", "Direct BTC purchase"),
    ("7", "29/08/2026", "5,00,000", "ICICI IMPS", "Direct BTC purchase"),
]:
    tx_rows.append([Paragraph(x, CELL) for x in (sl, date, amt, mode, dest)])
story.append(grid(tx_rows, [1.2 * cm, 2.8 * cm, 3.0 * cm, 3.6 * cm, 6.2 * cm]))
story.append(Spacer(1, 4))
story.append(Paragraph(
    "<b>Total: Rs. 47,50,000/-</b> (Rupees Forty Seven Lakh Fifty Thousand only). "
    f"All amounts were converted to Bitcoin and remitted to wallet {SUSPECT}.", CELL))

story.append(Paragraph("7. BRIEF FACTS OF THE CASE", SEC))
story.append(Paragraph(
    "The complainant states that on 12/08/2026 he was added to a WhatsApp group titled "
    "\"AlphaQuant VIP Signals\" by an unknown person who introduced himself as a portfolio "
    "advisor. He was persuaded to register on the website www.alphaquant-invest[.]com, which "
    "displayed a professional trading dashboard showing daily returns of 3 to 5 percent.", BODY))
story.append(Spacer(1, 5))
story.append(Paragraph(
    "Between 12/08/2026 and 29/08/2026 the complainant transferred a total of "
    "Rs. 47,50,000/- in eleven instalments. He was directed to purchase Bitcoin through a "
    f"peer-to-peer platform and remit it to the wallet address {SUSPECT}. "
    "The dashboard reflected a balance of Rs. 71,20,000/- against these deposits.", BODY))
story.append(Spacer(1, 5))
story.append(Paragraph(
    "When the complainant attempted to withdraw on 30/08/2026 he was informed that a "
    "\"regulatory clearance fee\" of Rs. 8,00,000/- was payable in advance. On refusing, he was "
    "removed from the group, the advisor's numbers became unreachable and the website ceased "
    "to resolve. The complainant thereafter registered complaint "
    "NCRP/2026/KA/0004471 on the National Cyber Crime Reporting Portal.", BODY))
story.append(Spacer(1, 5))
story.append(Paragraph(
    "It is prayed that the said wallet address be traced through blockchain analysis, the "
    "recipient virtual asset service provider be identified, and appropriate preservation and "
    "disclosure directions be issued under Section 94 of the Bharatiya Nagarik Suraksha "
    "Sanhita, 2023 for recovery of the defrauded amount.", BODY))

story.append(Paragraph("8. ACTION TAKEN", SEC))
story.append(Paragraph(
    "The above information having disclosed the commission of a cognizable offence, the case "
    "was registered and investigation was taken up. The digital asset particulars at Item 5 "
    "have been forwarded to the Cyber Forensic Analysis Unit for on-chain tracing.", BODY))

story.append(Spacer(1, 16))
sig = Table([[
    Paragraph("Signature / Thumb impression<br/>of the Complainant<br/><br/><br/>"
              "<b>(Ramesh Kumar Iyer)</b>", CELL),
    Paragraph("Signature of the Officer in Charge<br/><br/><br/>"
              "<b>Inspector of Police</b><br/>Cyber Crime Police Station<br/>"
              "Bengaluru City", CELL),
]], colWidths=[8.4 * cm, 8.4 * cm])
sig.setStyle(TableStyle([("VALIGN", (0, 0), (-1, -1), "TOP")]))
story.append(sig)

doc = SimpleDocTemplate(
    str(OUT_DIR / "FIR-0147-2026-Cyber-Crime-Bengaluru.pdf"),
    pagesize=A4, topMargin=1.5 * cm, bottomMargin=1.5 * cm,
    leftMargin=2 * cm, rightMargin=2 * cm,
    title="FIR 0147/2026 - Cyber Crime Police Station, Bengaluru City")
doc.build(story)
print("built")
