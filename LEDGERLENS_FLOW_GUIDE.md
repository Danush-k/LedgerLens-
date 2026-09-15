# LedgerLens — Simple Flow & Feature Guide

---

## 1. What This App Is For (Simple Summary)

When a person gets cheated in a crypto scam, the victim files a police complaint with a scammer's crypto wallet address. Police investigators need to find out **where that stolen money went** and **which crypto exchange (like Binance, WazirX, or CoinDCX) received the funds**, so they can quickly freeze the account before the scammer withdraws real cash. 

Checking thousands of blockchain transfers manually takes many hours or days. **LedgerLens** automatically follows the stolen money hop-by-hop across the blockchain in seconds, identifies the nearest exchange, rates the fraud risk, clusters linked scam wallets, and generates official legal notices for police action.

---

## 2. High-Level Flow (How the Whole App Works)

```
[1. Victim Complaint] ──> [2. Submit Wallet] ──> [3. Auto-Trace on Blockchain]
                                                              │
                                                              ▼
[6. Police Legal Notice] <── [5. Interactive Graph] <── [4. Identify Exchange & Risk]
```

1. **Step 1 — Complaint Intake:** Investigator receives a victim complaint with a suspect wallet address.
2. **Step 2 — Submit Trace:** Investigator inputs the wallet address (or uploads a CSV list of wallets).
3. **Step 3 — Automated Chain Hop:** The system queries live public blockchain data to follow every outgoing transfer hop-by-hop.
4. **Step 4 — Attribution & Risk:** The trace stops as soon as it hits a known exchange or mixer, and calculates a 0–100 risk score.
5. **Step 5 — Investigation & Clustering:** Investigator views the interactive transaction graph showing the exact money path and connected wallets.
6. **Step 6 — Legal Action:** Investigator generates a Section 91/94 legal notice or PDF report with a tamper-evident digital fingerprint to freeze the scammer's exchange account.

---

## 3. Page-by-Page Feature Guide

---

### Page 1: Login Page (`/login`)

#### Feature: Investigator Login
* **Go to:** `/login`
* **How to check:** Enter username `investigator` and password `changeme123`, then click **Sign In**.
* **What it is for:** Protects sensitive police case data so only authorized investigators can access the system.

---

### Page 2: Command Centre / Overview (`/`)

#### Feature 1: Convergence Alerts
* **Go to:** `/` (top alert card)
* **How to check:** Look at the top alert box showing wallets flagged across multiple complaints.
* **What it is for:** Instantly warns investigators if two or more separate victims were robbed by the exact same wallet.

#### Feature 2: Summary Stat Tiles
* **Go to:** `/` (the 5 top metric boxes)
* **How to check:** Review the numbers for *Total Cases*, *High Risk*, *Exchange Identified %*, *Average Risk*, and *Convergence*.
* **What it is for:** Gives a 2-second snapshot of your overall investigative workload and success rate.

#### Feature 3: Risk Distribution Bar
* **Go to:** `/` (first chart card)
* **How to check:** Look at the High, Medium, and Low risk colored horizontal bars.
* **What it is for:** Shows how dangerous your current active cases are based on automated fraud scoring.

#### Feature 4: Cases by Chain Bar
* **Go to:** `/` (second chart card)
* **How to check:** Review case counts divided by Ethereum, BSC, Polygon, and Bitcoin.
* **What it is for:** Shows which blockchain network scammers are using the most.

#### Feature 5: Fraud Typologies Bar
* **Go to:** `/` (third chart card)
* **How to check:** See categories like Investment Scam, Phishing, Ransomware, or Sextortion.
* **What it is for:** Categorizes criminal scam methods automatically extracted from complaint stories.

#### Feature 6: Destination Exchanges Bar
* **Go to:** `/` (fourth chart card)
* **How to check:** View top exchanges like Binance, OKX, or Huobi listed with case counts.
* **What it is for:** Highlights which crypto exchanges receive stolen funds most frequently.

#### Feature 7: Recent High-Risk Cases Table
* **Go to:** `/` (bottom table)
* **How to check:** View the list of urgent cases with a risk score ≥ 50, and click any wallet to open it.
* **What it is for:** Directs investigator attention to the most critical cases that need immediate freezing.

---

### Page 3: New Trace (`/new`)

#### Feature 1: Smart Complaint Parser
* **Go to:** `/new` (top text box)
* **How to check:** Paste an unformatted police FIR text or email message and click **Extract Details**.
* **What it is for:** Automatically extracts the wallet address, blockchain network, reference number, and story using AI without manual typing.

#### Feature 2: Manual Wallet & Chain Selector
* **Go to:** `/new` (form fields)
* **How to check:** Select Ethereum, BSC, Polygon, or Bitcoin, and paste the wallet address into the box.
* **What it is for:** Allows manual entry of a suspect address when you already have the exact details.

#### Feature 3: Live Address Format Validator
* **Go to:** `/new` (address input field)
* **How to check:** Type an incorrect address (e.g. missing `0x` or wrong length) to see an instant warning.
* **What it is for:** Prevents human typo errors before initiating a blockchain search.

#### Feature 4: Trace Submission
* **Go to:** `/new` (bottom button)
* **How to check:** Click **Start Trace** to begin the background analysis.
* **What it is for:** Starts the live blockchain tracing engine and takes you directly to the Case Detail page.

---

### Page 4: Bulk Wallet Upload (`/bulk`)

#### Feature 1: CSV File Upload & Drag-and-Drop
* **Go to:** `/bulk` (drop zone)
* **How to check:** Drag a CSV file containing wallet addresses into the dotted box.
* **What it is for:** Lets investigators submit up to 200 suspect wallets at once instead of one by one.

#### Feature 2: Download Sample CSV
* **Go to:** `/bulk`
* **How to check:** Click the **Download sample CSV** button to download a ready-made template file.
* **What it is for:** Shows the exact column format needed (`address`, `chain`, `complaint_ref`, `narrative`).

#### Feature 3: Batch Results Breakdown
* **Go to:** `/bulk` (after upload)
* **How to check:** Look at the green "Accepted" list and red "Rejected" list with error reasons.
* **What it is for:** Verifies which wallets were successfully queued and explains why any invalid rows failed.

---

### Page 5: Case Directory (`/cases`)

#### Feature 1: Search Bar & Multi-Filters
* **Go to:** `/cases` (filter bar at top)
* **How to check:** Type an address in the search box, or filter by chain, status, or minimum risk score.
* **What it is for:** Quickly narrows down hundreds of cases to find the exact complaint you need.

#### Feature 2: Sortable Columns
* **Go to:** `/cases` (table headers)
* **How to check:** Click headers like **Wallet**, **Risk**, or **Reported** to toggle ascending/descending order.
* **What it is for:** Reorders cases to review the highest risk or newest cases first.

#### Feature 3: Export to CSV
* **Go to:** `/cases` (top right)
* **How to check:** Click the **Export CSV** button.
* **What it is for:** Downloads your filtered investigation list into an Excel/CSV file for external reporting.

---

### Page 6: Case Detail (`/cases/:id`)

#### Feature 1: Interactive Transaction Graph
* **Go to:** `/cases/:id` (main top visual area)
* **How to check:** Click, drag, zoom in/out, and click any circle (node) on the graph.
* **What it is for:** Visually maps how money flowed from the victim's wallet through intermediary wallets to the exchange.

#### Feature 2: Target Route Highlighting (Golden Path)
* **Go to:** `/cases/:id` (transaction graph)
* **How to check:** Observe the colored highlighted path running directly from the suspect wallet to the exchange.
* **What it is for:** Instantly reveals the shortest, most critical trail of stolen funds without visual clutter.

#### Feature 3: Node Inspector
* **Go to:** `/cases/:id` (click any node in the graph)
* **How to check:** Click any address circle to open the right-side inspection drawer.
* **What it is for:** Displays the full wallet address, tags (Exchange, Mixer, Suspect), balance, and external explorer link.

#### Feature 4: Target VASP / Nearest Exchange Card
* **Go to:** `/cases/:id` (left card below graph)
* **How to check:** View the exchange name (e.g. Binance), its deposit address, and hop distance.
* **What it is for:** Tells police exactly which company to contact and which deposit address to freeze.

#### Feature 5: Recommended Action
* **Go to:** `/cases/:id` (inside Nearest Exchange card)
* **How to check:** Read the highlighted recommendation text at the bottom of the card.
* **What it is for:** Gives the investigator clear instructions on what legal notice to issue next.

#### Feature 6: Risk Assessment Gauge & Detected Flags
* **Go to:** `/cases/:id` (right card below graph)
* **How to check:** Look at the speedometer-style 0–100 risk dial and read badge tags like `mixer_detected` or `high_fan_out`.
* **What it is for:** Provides an objective, explainable score showing how likely the wallet is tied to organized crime.

#### Feature 7: Forensic Findings Panel
* **Go to:** `/cases/:id` (Findings section)
* **How to check:** Review specific detected money-laundering patterns alongside their real blockchain transaction hashes.
* **What it is for:** Supplies the concrete transaction hash proof required in court affidavits.

#### Feature 8: Wallet Clusters Panel
* **Go to:** `/cases/:id` (Clusters section)
* **How to check:** See addresses grouped together under common ownership heuristics.
* **What it is for:** Identifies all other secret wallets owned by the same criminal actor.

#### Feature 9: Related Cases Panel
* **Go to:** `/cases/:id` (Related cases section)
* **How to check:** Look at linked complaints sharing the same wallets or patterns.
* **What it is for:** Connects separate police complaints together into a single organized crime syndicate case.

#### Feature 10: Legal Notice Generator (Sec 91 / 94)
* **Go to:** `/cases/:id` (top right button: **Generate Legal Notice**)
* **How to check:** Click the button, select notice type (Section 91 for records, Section 94 for freeze), and click **Download Notice**.
* **What it is for:** Generates a ready-to-sign formal legal order to compel the exchange to freeze the scammer's crypto.

#### Feature 11: Evidence Hash Verifier
* **Go to:** `/cases/:id` (top right button: **Verify Hash**)
* **How to check:** Click the button to inspect the SHA-256 digital fingerprint of the case data.
* **What it is for:** Proves in court that the evidence report has not been altered or tampered with since investigation.

#### Feature 12: Audit Chain Panel
* **Go to:** `/cases/:id` (bottom section)
* **How to check:** Read the chronological chain-of-custody audit log of all system and user actions.
* **What it is for:** Guarantees forensic accountability and satisfies judicial chain-of-custody requirements.

---

### Page 7: Network Explorer (`/network`)

#### Feature 1: Convergence Points Tab
* **Go to:** `/network` (select **Convergence Points** tab)
* **How to check:** View wallets that received money from 2 or more different complaints, with a slider to adjust minimum cases.
* **What it is for:** Uncovers main scam collection hubs and money-mule consolidation wallets across the country.

#### Feature 2: Entities Tab
* **Go to:** `/network` (select **Entities** tab)
* **How to check:** Browse multi-wallet clusters grouped by algorithmic co-spending heuristics.
* **What it is for:** Maps entire scam syndicate infrastructure rather than isolated single wallets.

#### Feature 3: Network Search
* **Go to:** `/network` (search bar)
* **How to check:** Type any wallet address or complaint ID to see where it connects across all cases.
* **What it is for:** Quickly reveals if a newly reported suspect was part of previous investigations.

---

### Global Features (Available on Every Page)

#### Feature 1: Quick Command Palette (`Cmd + K` or `Ctrl + K`)
* **How to check:** Press `Cmd + K` on Mac (or `Ctrl + K` on Windows/Linux), or click the search bar in the top navigation header.
* **What it is for:** Lets investigators instantly jump to any case, page, or action using only the keyboard.

#### Feature 2: Dark / Light Mode Toggle
* **How to check:** Click the Sun/Moon icon in the top navigation bar.
* **What it is for:** Switches the visual theme between clean light mode and high-contrast dark mode for low-light rooms.
