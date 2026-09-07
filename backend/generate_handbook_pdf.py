import sys
from reportlab.lib.pagesizes import A4
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak, KeepTogether, HRFlowable
)
from reportlab.pdfgen import canvas

class NumberedCanvas(canvas.Canvas):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved_page_states = []

    def showPage(self):
        self._saved_page_states.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        num_pages = len(self._saved_page_states)
        for state in self._saved_page_states:
            self.__dict__.update(state)
            self.draw_header_footer(num_pages)
            super().showPage()
        super().save()

    def draw_header_footer(self, page_count):
        self.saveState()
        self.setFont("Helvetica", 8)
        self.setFillColor(colors.HexColor("#64748b"))
        
        # Header (on pages 2+)
        if self._pageNumber > 1:
            self.drawString(54, 800, "LedgerLens — Crypto Fundamentals & Investigation Handbook")
            self.setStrokeColor(colors.HexColor("#e2e8f0"))
            self.setLineWidth(0.5)
            self.line(54, 792, 541, 792)

        # Footer
        self.setStrokeColor(colors.HexColor("#e2e8f0"))
        self.setLineWidth(0.5)
        self.line(54, 45, 541, 45)
        self.drawString(54, 32, "Confidential — For Training & Investigation Team Reference")
        self.drawRightString(541, 32, f"Page {self._pageNumber} of {page_count}")
        self.restoreState()

def create_pdf(output_path):
    doc = SimpleDocTemplate(
        output_path,
        pagesize=A4,
        leftMargin=54,
        rightMargin=54,
        topMargin=54,
        bottomMargin=54
    )

    styles = getSampleStyleSheet()
    
    # Custom styles
    primary_color = colors.HexColor("#0f172a") # dark slate
    brand_blue = colors.HexColor("#1d4ed8")   # blue
    text_color = colors.HexColor("#334155")
    card_bg = colors.HexColor("#f8fafc")
    border_color = colors.HexColor("#cbd5e1")

    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Title'],
        fontName='Helvetica-Bold',
        fontSize=22,
        leading=26,
        textColor=primary_color,
        alignment=0,
        spaceAfter=4
    )

    subtitle_style = ParagraphStyle(
        'DocSubtitle',
        fontName='Helvetica',
        fontSize=11,
        leading=15,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=14
    )

    h1_style = ParagraphStyle(
        'SectionH1',
        fontName='Helvetica-Bold',
        fontSize=13,
        leading=17,
        textColor=brand_blue,
        spaceBefore=12,
        spaceAfter=6,
        keepWithNext=True
    )

    h2_style = ParagraphStyle(
        'SectionH2',
        fontName='Helvetica-Bold',
        fontSize=10.5,
        leading=14,
        textColor=primary_color,
        spaceBefore=8,
        spaceAfter=4,
        keepWithNext=True
    )

    body_style = ParagraphStyle(
        'BodyDark',
        fontName='Helvetica',
        fontSize=9,
        leading=13,
        textColor=text_color,
        spaceAfter=6
    )

    body_bold = ParagraphStyle(
        'BodyDarkBold',
        parent=body_style,
        fontName='Helvetica-Bold'
    )

    bullet_style = ParagraphStyle(
        'BulletText',
        parent=body_style,
        leftIndent=14,
        firstLineIndent=-10,
        spaceAfter=3
    )

    table_header = ParagraphStyle(
        'TableHeader',
        fontName='Helvetica-Bold',
        fontSize=8.5,
        leading=11,
        textColor=colors.white
    )

    table_cell = ParagraphStyle(
        'TableCell',
        fontName='Helvetica',
        fontSize=8,
        leading=11,
        textColor=text_color
    )

    table_cell_bold = ParagraphStyle(
        'TableCellBold',
        parent=table_cell,
        fontName='Helvetica-Bold',
        textColor=primary_color
    )

    code_cell = ParagraphStyle(
        'CodeCell',
        fontName='Courier',
        fontSize=7.5,
        leading=9.5,
        textColor=colors.HexColor("#0f172a")
    )

    callout_text = ParagraphStyle(
        'CalloutText',
        fontName='Helvetica',
        fontSize=8.5,
        leading=12,
        textColor=colors.HexColor("#1e293b")
    )

    story = []

    # Title & Subtitle
    story.append(Paragraph("LedgerLens — Crypto Fundamentals & Investigation Handbook", title_style))
    story.append(Paragraph("A Complete Zero-Knowledge Guide to Cryptocurrencies, Blockchain Terminology, and Forensic Attribution Mechanics", subtitle_style))
    story.append(HRFlowable(width="100%", thickness=1.5, color=brand_blue, spaceBefore=0, spaceAfter=12))

    # SECTION 1
    story.append(Paragraph("1. What is Cryptocurrency & Blockchain? (Core Concepts)", h1_style))
    
    story.append(Paragraph("<b>1.1 What is Cryptocurrency?</b>", h2_style))
    story.append(Paragraph(
        "Cryptocurrency is digital money that operates without any central authority, bank, or government. Unlike fiat money (like Indian Rupees or US Dollars) which is controlled by the Reserve Bank of India or Federal Reserve, crypto is managed mathematically by open computer networks.",
        body_style
    ))

    story.append(Paragraph("<b>1.2 What is a Blockchain?</b>", h2_style))
    story.append(Paragraph(
        "A blockchain is a digital, public, and unalterable account book (ledger) shared across thousands of computers worldwide.",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Blocks:</b> Packages containing groups of verified transactions.", bullet_style))
    story.append(Paragraph("&bull; <b>Chain:</b> Each block contains a cryptographic link to the previous block, forming an unbroken timeline.", bullet_style))
    story.append(Paragraph("&bull; <b>Immutable & Public:</b> Once written, transactions can <b>never be modified or erased</b>. Every person on earth can inspect every transaction that ever occurred.", bullet_style))

    story.append(Paragraph("<b>1.3 Do Bitcoin and Ethereum Have Different Chains and Blocks?</b>", h2_style))
    story.append(Paragraph(
        "<b>Yes, completely separate networks.</b> Bitcoin (BTC) operates on its own dedicated Bitcoin blockchain. Ethereum (ETH) operates on the separate Ethereum blockchain. Binance Smart Chain (BSC) and Polygon are also independent networks. A Bitcoin wallet cannot directly receive Ethereum, and their blocks and transaction ledgers are completely independent.",
        body_style
    ))

    story.append(Spacer(1, 6))

    # SECTION 2
    story.append(Paragraph("2. Essential Crypto Terminology Dictionary", h1_style))
    story.append(Paragraph("Key definitions every team member and investigator must know:", body_style))

    terms_data = [
        [
            Paragraph("Term", table_header),
            Paragraph("What It Means (Simple Analogy)", table_header),
            Paragraph("Real Format / Example", table_header)
        ],
        [
            Paragraph("Wallet Address<br/>(Wallet ID)", table_cell_bold),
            Paragraph("Digital equivalent of a <b>Bank Account Number</b>. Publicly visible. Anyone can send funds to it.", table_cell),
            Paragraph("ETH: 0xeb2d2f...c8a0bb<br/>BTC: bc1qg24y...6h8jp", code_cell)
        ],
        [
            Paragraph("Private Key", table_cell_bold),
            Paragraph("Digital equivalent of your <b>ATM PIN / Secret Password</b>. Grants full power to move funds. Scammers never reveal this.", table_cell),
            Paragraph("64-character hex secret (kept strictly private)", code_cell)
        ],
        [
            Paragraph("Transaction Hash<br/>(Tx Hash / TxID)", table_cell_bold),
            Paragraph("The unique <b>receipt number (UTR)</b> for a single transfer. Proves sender, recipient, amount, and timestamp.", table_cell),
            Paragraph("0x4a8f9c2d1b... (64 hex characters)", code_cell)
        ],
        [
            Paragraph("Evidence Hash<br/>(SHA-256)", table_cell_bold),
            Paragraph("A mathematical <b>digital fingerprint</b> of the entire case file. Proves in court that evidence was not altered after generation.", table_cell),
            Paragraph("e3b0c44298fc1c149af... (64 chars)", code_cell)
        ],
        [
            Paragraph("Hop", table_cell_bold),
            Paragraph("One movement of crypto from one wallet to another. Wallet A &rarr; B = 1 Hop. A &rarr; B &rarr; C = 2 Hops.", table_cell),
            Paragraph("Hop 1, Hop 2, Hop 3...", table_cell)
        ],
        [
            Paragraph("Multi-Hop Trace", table_cell_bold),
            Paragraph("Tracking money through multiple intermediary wallets (mules) as the scammer attempts to wash the paper trail.", table_cell),
            Paragraph("Victim &rarr; Mule 1 &rarr; Mule 2 &rarr; VASP", table_cell)
        ],
        [
            Paragraph("Exchange / VASP", table_cell_bold),
            Paragraph("<b>Virtual Asset Service Provider</b> (like Binance, WazirX, CoinDCX). A centralized platform where users swap crypto for real bank cash.", table_cell),
            Paragraph("Binance, CoinDCX, WazirX, OKX, Kraken", table_cell)
        ],
        [
            Paragraph("Nearest Exchange", table_cell_bold),
            Paragraph("The first verified crypto exchange deposit address encountered along the forward money trail.", table_cell),
            Paragraph("e.g. Binance Deposit at Hop 2", table_cell)
        ],
        [
            Paragraph("Mixer / Tumbler", table_cell_bold),
            Paragraph("An illicit service (e.g. Tornado Cash) that pools dirty crypto with clean coins to break forensic attribution. A high-risk flag.", table_cell),
            Paragraph("Smart contract mixer (Flag: mixer_detected)", table_cell)
        ],
        [
            Paragraph("Cross-Chain Bridge", table_cell_bold),
            Paragraph("Software protocols allowing funds to jump from one blockchain to another (e.g. Ethereum to BSC).", table_cell),
            Paragraph("Bridge protocol (Flag: bridge_detected)", table_cell)
        ],
    ]

    col_widths = [100, 225, 162]
    terms_table = Table(terms_data, colWidths=col_widths, repeatRows=1)
    terms_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 4),
        ('TOPPADDING', (0, 0), (-1, -1), 4),
        ('LEFTPADDING', (0, 0), (-1, -1), 5),
        ('RIGHTPADDING', (0, 0), (-1, -1), 5),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(terms_table)

    story.append(PageBreak())

    # SECTION 3
    story.append(Paragraph("3. How Police Attribution Works (Unmasking the Scammer)", h1_style))
    story.append(Paragraph(
        "A common point of confusion is: <i>If blockchain addresses are anonymous strings of numbers and letters, how does LedgerLens help police catch the actual human criminal?</i>",
        body_style
    ))

    # Callout box
    callout_data = [[
        Paragraph(
            "<b>The Core Forensic Principle:</b><br/>"
            "Blockchains are <b>pseudonymous</b>, not anonymous. While a wallet address does not contain a person's name, scammers cannot spend raw crypto at grocery stores or for bank deposits. Eventually, they must transfer stolen crypto to a centralized <b>Exchange (VASP)</b> to cash out into fiat currency (INR/USD).",
            callout_text
        )
    ]]
    callout_table = Table(callout_data, colWidths=[487])
    callout_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, -1), colors.HexColor("#eff6ff")),
        ('BOX', (0, 0), (-1, -1), 1, colors.HexColor("#bfdbfe")),
        ('TOPPADDING', (0, 0), (-1, -1), 8),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 8),
        ('LEFTPADDING', (0, 0), (-1, -1), 10),
        ('RIGHTPADDING', (0, 0), (-1, -1), 10),
    ]))
    story.append(callout_table)
    story.append(Spacer(1, 8))

    story.append(Paragraph("<b>Step-by-Step Investigative Pipeline:</b>", h2_style))
    story.append(Paragraph("1. <b>Victim Files Complaint:</b> The victim reports the suspect address where they sent their crypto.", bullet_style))
    story.append(Paragraph("2. <b>LedgerLens Automated Walk:</b> The tracing engine follows outgoing transactions hop-by-hop.", bullet_style))
    story.append(Paragraph("3. <b>Target Exchange Identified:</b> The trace stops when it hits a known exchange deposit wallet (e.g. Binance at Hop 2).", bullet_style))
    story.append(Paragraph("4. <b>Mandatory KYC Records:</b> Regulated exchanges require government identity verification (Aadhaar, PAN, Passport, Bank Account, Phone, IP logs) to open an account.", bullet_style))
    story.append(Paragraph("5. <b>Legal Notice Issued:</b> Police generate a formal <b>Section 91 / 94 CrPC (or BNSS)</b> notice ordering the exchange to freeze the account and provide the account owner's real-world identity.", bullet_style))

    story.append(Spacer(1, 8))

    # SECTION 4
    story.append(Paragraph("4. Key Advanced Concepts Explained", h1_style))

    story.append(Paragraph("<b>4.1 Fraud Typology</b>", h2_style))
    story.append(Paragraph(
        "Typology represents the operational narrative or scam technique used against the victim. LedgerLens uses rule-based NLP to automatically extract the typology from the complaint text: <b>Investment Scam</b> (fake trading platforms), <b>Task-Based Fraud</b> (Telegram rating scams), <b>Phishing</b> (fake links/wallet drainers), <b>Sextortion</b> (blackmail), and <b>Ransomware</b>.",
        body_style
    ))

    story.append(Paragraph("<b>4.2 Convergence & Convergence Points</b>", h2_style))
    story.append(Paragraph(
        "When hundreds of independent complaints are submitted across different districts, individual officers only see their single victim's wallet. LedgerLens examines all cases collectively. If Victim 1 in Delhi and Victim 2 in Mumbai both had their funds routed into the same intermediate wallet 2 hops away, that wallet is flagged as a <b>Convergence Point</b>. This is definitive proof of an <b>organized cybercrime syndicate</b>.",
        body_style
    ))

    story.append(Paragraph("<b>4.3 Clustering Heuristics (Finding Hidden Wallets)</b>", h2_style))
    story.append(Paragraph(
        "Clustering groups distinct addresses that belong to the same human actor:",
        body_style
    ))
    story.append(Paragraph("&bull; <b>Common-Input-Ownership (Bitcoin):</b> In Bitcoin, transactions can combine inputs from multiple wallets. To execute such a transfer, the sender must possess the private keys to all input wallets simultaneously. Therefore, all co-spent addresses are owned by the exact same actor.", bullet_style))
    story.append(Paragraph("&bull; <b>Shared-Funder Fan-Out (Any Chain):</b> If one central wallet sends initial gas/funds to 10 brand-new addresses simultaneously, those recipient addresses are identified as connected mule accounts.", bullet_style))

    story.append(Spacer(1, 8))

    # SECTION 5
    story.append(Paragraph("5. Real Data vs. Mock Data: Where Does Data Come From?", h1_style))

    data_breakdown = [
        [
            Paragraph("Component", table_header),
            Paragraph("Status", table_header),
            Paragraph("Where Data is Sourced From", table_header)
        ],
        [
            Paragraph("Blockchain Transactions", table_cell_bold),
            Paragraph("<b>100% REAL LIVE DATA</b>", table_cell),
            Paragraph("Direct live public APIs: <b>Blockstream</b> (Bitcoin), <b>Etherscan</b> (Ethereum), <b>BscScan</b> (BSC), <b>PolygonScan</b> (Polygon). Every tx hash and amount is genuine on-chain history.", table_cell)
        ],
        [
            Paragraph("Exchange & VASP Labels", table_cell_bold),
            Paragraph("<b>Curated Public Starter Set</b>", table_cell),
            Paragraph("Verified public exchange deposit addresses and mixer contracts sourced from public chain analytics (Etherscan, BitInfoCharts, WalletLabels).", table_cell)
        ],
        [
            Paragraph("External Portals (NCRP/LEA)", table_cell_bold),
            Paragraph("<b>Simulated Connector</b>", table_cell),
            Paragraph("Clearly marked simulation stubs for national cybercrime reporting portals (NCRP/SAHYOG), as live access requires government intranet network clearance.", table_cell)
        ],
    ]

    data_table = Table(data_breakdown, colWidths=[130, 110, 247])
    data_table.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor("#1e293b")),
        ('ALIGN', (0, 0), (-1, -1), 'LEFT'),
        ('VALIGN', (0, 0), (-1, -1), 'TOP'),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.white),
        ('BOTTOMPADDING', (0, 0), (-1, -1), 5),
        ('TOPPADDING', (0, 0), (-1, -1), 5),
        ('LEFTPADDING', (0, 0), (-1, -1), 6),
        ('RIGHTPADDING', (0, 0), (-1, -1), 6),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.HexColor("#e2e8f0")),
        ('ROWBACKGROUNDS', (0, 1), (-1, -1), [colors.white, colors.HexColor("#f8fafc")]),
    ]))
    story.append(data_table)

    doc.build(story, canvasmaker=NumberedCanvas)
    print(f"PDF successfully created at: {output_path}")

if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else "LedgerLens-Crypto-Beginners-Handbook.pdf"
    create_pdf(out)
