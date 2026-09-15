"""The same FIR as a Word document.

Complaints arrive in both formats, and the two exercise different code
paths: PDF goes through a text-layer extractor, Word through paragraph and
table reads. FIR forms are overwhelmingly tables, so this file is built as
tables deliberately - a paragraph-only reader would return almost nothing
from it, which is the failure the docx path is written to avoid.

Run with the backend virtualenv from the project root:

    backend/.venv/bin/python fir/generate_fir_docx.py
"""
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.shared import Pt

SUSPECT = "1CRLGcaXajtWVF5EopZgQUqE12dKn8Rtuh"
OUT = Path(__file__).resolve().parent / "FIR-0148-2026-Cyber-Crime-Hyderabad.docx"

d = docx.Document()
for section in d.sections:
    section.top_margin = section.bottom_margin = docx.shared.Cm(1.8)

title = d.add_paragraph()
title.alignment = WD_ALIGN_PARAGRAPH.CENTER
run = title.add_run("FIRST INFORMATION REPORT")
run.bold = True
run.font.size = Pt(14)

sub = d.add_paragraph()
sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
sub_run = sub.add_run(
    "(Under Section 173 Bharatiya Nagarik Suraksha Sanhita, 2023)\n"
    "Integrated Form IF1-A  ·  Cyber Crime Police Station, Hyderabad City")
sub_run.font.size = Pt(9)


def heading(text: str) -> None:
    p = d.add_paragraph()
    r = p.add_run(text)
    r.bold = True
    r.font.size = Pt(10)


def kv_table(rows: list[tuple[str, str]]) -> None:
    t = d.add_table(rows=len(rows), cols=2)
    t.style = "Table Grid"
    for i, (k, v) in enumerate(rows):
        t.cell(i, 0).text = k
        t.cell(i, 1).text = v
        for cell in t.rows[i].cells:
            for p in cell.paragraphs:
                for r in p.runs:
                    r.font.size = Pt(9)
        for r in t.cell(i, 0).paragraphs[0].runs:
            r.bold = True


heading("1. DISTRICT / POLICE STATION / FIR PARTICULARS")
kv_table([
    ("District", "Hyderabad City"),
    ("Police Station", "Cyber Crime Police Station, Banjara Hills"),
    ("FIR No.", "0148/2026"),
    ("Date & Time of FIR", "05/09/2026 at 15:40 hrs"),
    ("NCRP Acknowledgement No.", "NCRP/2026/TS/0009312"),
])

heading("2. ACTS AND SECTIONS")
kv_table([
    ("Bharatiya Nyaya Sanhita, 2023",
     "Sections 318(4) (cheating), 319(2) (cheating by personation)"),
    ("Information Technology Act, 2000",
     "Sections 66C (identity theft), 66D (cheating by personation)"),
])

heading("3. COMPLAINANT / INFORMANT")
kv_table([
    ("Name", "Priya Venkatesh"),
    ("Age / Occupation", "34 years / Chartered Accountant"),
    ("Address", "Flat 6B, Aparna Towers, Gachibowli, Hyderabad - 500032"),
    ("Mobile / Email", "+91 99490 xxxxx / p.venkatesh@example.com"),
])

heading("4. PARTICULARS OF THE OFFENCE")
kv_table([
    ("Date / Period of Offence", "18/08/2026 to 31/08/2026"),
    ("Place of Occurrence", "Online / Cyberspace"),
    ("Total Amount Defrauded",
     "Rs. 22,00,000/- (Rupees Twenty Two Lakh only)"),
    ("Mode of Payment", "Bank transfer converted to Bitcoin (BTC)"),
])

heading("5. SUSPECT / DIGITAL ASSET DETAILS")
kv_table([
    ("Suspect Wallet Address (BTC)", SUSPECT),
    ("Blockchain Network", "Bitcoin (BTC) mainnet"),
    ("Suspect Platform", "\"Meridian Yield\" - www.meridian-yield[.]io (offline)"),
    ("Suspect Contact", "Telegram @meridian_desk"),
])

heading("6. BRIEF FACTS OF THE CASE")
for para in [
    "The complainant states that on 18/08/2026 she was contacted on Telegram by a "
    "person claiming to represent Meridian Yield, an entity purportedly offering "
    "arbitrage returns on stablecoin holdings. She was directed to a dashboard at "
    "www.meridian-yield[.]io which displayed her deposits accruing daily returns.",

    "Between 18/08/2026 and 31/08/2026 the complainant transferred Rs. 22,00,000/- "
    "in six instalments. On each occasion she was instructed to purchase Bitcoin "
    f"and remit it to the wallet address {SUSPECT}.",

    "When she sought to withdraw on 01/09/2026 she was told a \"liquidity unlock "
    "deposit\" of Rs. 4,00,000/- was required. On declining, all contact ceased and "
    "the platform became unreachable. The complainant registered complaint "
    "NCRP/2026/TS/0009312 on the National Cyber Crime Reporting Portal.",

    "It is prayed that the said wallet be traced through blockchain analysis, the "
    "recipient virtual asset service provider identified, and preservation and "
    "disclosure directions issued under Section 94 of the Bharatiya Nagarik "
    "Suraksha Sanhita, 2023.",
]:
    p = d.add_paragraph(para)
    for r in p.runs:
        r.font.size = Pt(9)

heading("7. ACTION TAKEN")
p = d.add_paragraph(
    "The information disclosing a cognizable offence, the case was registered and "
    "investigation taken up. The digital asset particulars at Item 5 have been "
    "referred to the Cyber Forensic Analysis Unit for on-chain tracing.")
for r in p.runs:
    r.font.size = Pt(9)

d.save(OUT)
print(f"built {OUT.name}")
