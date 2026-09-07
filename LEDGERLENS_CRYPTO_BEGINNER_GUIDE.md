# Cryptocurrency & Blockchain Investigation: Beginner Handbook
### Comprehensive Guide to Blockchain Fundamentals, Crypto Terminology, and the LedgerLens Attribution Pipeline

---

## 1. What is Cryptocurrency and Blockchain?

### 1.1 What is Cryptocurrency?
Cryptocurrency is digital money that does not rely on a central bank, government, or payment processor (like Visa or MasterCard). Instead, transactions are verified and secured mathematically by a decentralized network of computers worldwide.

### 1.2 What is a Blockchain?
A blockchain is a digital ledger (an open account book) distributed across thousands of computers.
* **Blocks:** Groups of recent transactions bundled together.
* **Chain:** Every new block is mathematically linked to the previous block using cryptography, forming an unbroken chain.
* **Public & Immutable:** Once a transaction is written into a block, it can **never be deleted or altered**. Anyone in the world can inspect every transaction that has occurred since the first day the blockchain went live.

### 1.3 Do Bitcoin and Ethereum Have Different Chains and Blocks?
**Yes, completely different.**
* **Bitcoin (BTC)** runs on the **Bitcoin blockchain**. Its blocks only record Bitcoin transfers and use the UTXO (Unspent Transaction Output) model.
* **Ethereum (ETH)** runs on the **Ethereum blockchain**. It has its own blocks, supports programmable smart contracts, and uses an account-balance model.
* **Binance Smart Chain (BSC)** and **Polygon** are separate EVM-compatible blockchains with their own distinct ledgers and validators.
* **Key Rule:** An address on Bitcoin (`bc1q...`, `1...`, `3...`) cannot send funds directly to an address on Ethereum (`0x...`). They are separate worlds.

---

## 2. Fundamental Crypto Terminology

| Term | What It Means (Simple Analogy) | Real Example / Format |
| :--- | :--- | :--- |
| **Wallet Address / Wallet ID** | The digital equivalent of a **bank account number**. You give it to others so they can send you crypto. Anyone can see its balance and transaction history on the public ledger. | `0xeb2d2f1b8c558a40207669291fda468e50c8a0bb` (ETH)<br>`bc1qg24yztysu68rj5vqszpka5cfl04w49h296h8jp` (BTC) |
| **Private Key** | The digital equivalent of your **ATM PIN / NetBanking password**. Whoever possesses the private key controls the wallet and can spend its funds. Scammers never share this. | Secret alphanumeric string (never shared). |
| **Transaction Hash (Tx Hash / TxID)** | The unique digital tracking receipt for a single transfer (like a bank UTR number). Proves who sent what amount to whom, and at what exact second. | `0x4a8f9c...` (64 hexadecimal characters) |
| **Evidence Hash (SHA-256)** | A mathematical digital fingerprint calculated over the entire case report. If even a single character in the report is changed, the hash changes completely, proving in court whether evidence has been tampered with. | `e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855` |
| **Hop** | One transfer step from one wallet to another. | Wallet A $\rightarrow$ Wallet B = **1 Hop**.<br>Wallet A $\rightarrow$ Wallet B $\rightarrow$ Wallet C = **2 Hops**. |
| **Multi-Hop Trace** | Following stolen crypto as the scammer moves it through multiple intermediate wallets to hide the paper trail. | Victim $\rightarrow$ Mule 1 $\rightarrow$ Mule 2 $\rightarrow$ Mule 3 $\rightarrow$ Exchange |
| **Exchange / VASP** | Virtual Asset Service Provider. A centralized crypto company (like Binance, WazirX, CoinDCX, Kraken) where users can trade crypto and cash out into real-world bank accounts (INR/USD). | Binance, CoinDCX, WazirX, OKX, Kraken |
| **Nearest Exchange** | The first known exchange deposit wallet reached along the money trail from the suspect's address. | e.g. Binance Hot Wallet at Hop 2 |
| **Crypto Mixer / Tumbler** | An illicit laundering service (e.g. Tornado Cash) that mixes dirty crypto with millions of clean coins from other users to obscure ownership. | Huge red flag in fraud investigations. |
| **Cross-Chain Bridge** | A software service allowing users to lock crypto on one blockchain and receive wrapped tokens on another blockchain. | e.g. moving funds from Ethereum to BSC. |

---

## 3. How Does Police Attribution Work? (Catching the Scammer)

### 3.1 Can We See the Scammer's Real Name on the Blockchain?
**No.** Blockchains are **pseudonymous**. A wallet address looks like `0x71C...3a9`. There are no names, Aadhaar numbers, or email addresses recorded on the blockchain itself.

### 3.2 If Addresses Are Anonymous, How Do We Catch the Criminal?
Criminals cannot buy groceries, cars, or property with raw cryptocurrency directly in the real world. Eventually, the scammer wants **real cash (fiat money like INR or USD)** deposited into their personal bank account.

To convert crypto into cash, the scammer must send the stolen crypto to an **Exchange (VASP)** like Binance or CoinDCX.
1. **Mandatory KYC:** Crypto exchanges are legally regulated financial institutions. To open an account, users must submit **KYC (Know Your Customer)**: Aadhaar card, PAN card, passport, selfie verification, linked bank account, phone number, and IP address logs.
2. **Attribution Strategy:**
   * LedgerLens follows the stolen crypto hop-by-hop until it hits an exchange deposit address.
   * LedgerLens identifies: *"The funds arrived at Binance deposit wallet `0x123...` 2 hops away."*
   * Police immediately issue a formal **Section 91 / 94 CrPC (or BNSS)** legal notice to Binance.
   * Binance freezes the scammer's exchange balance and hands over the verified KYC identity and bank details to law enforcement.

---

## 4. Advanced Concepts Explained Simply

### 4.1 What is Fraud Typology?
The specific **scam technique or narrative** used by fraudsters to deceive the victim.
LedgerLens automatically analyzes the complaint story and categorizes it:
* **Investment Scam:** Fake trading platforms, guaranteed daily returns, "crypto doubling" schemes.
* **Task-Based Fraud:** "Like YouTube videos / rate hotels on Telegram to earn money" scams.
* **Phishing:** Fake websites, malicious smart contract approvals, stolen seed phrases.
* **Sextortion / Blackmail:** Extortion emails threatening to leak compromised photos unless crypto is paid.
* **Ransomware:** Malware encrypting files and demanding crypto payment to release the key.

### 4.2 What is Convergence?
* **Problem:** In large cybercrime syndicates, hundreds of victims across different states report different scammer wallets.
* **How Convergence Works:** LedgerLens analyzes all active traces collectively. If funds from a complaint in Delhi and a complaint in Chennai both funnel into the exact same intermediary wallet 2 hops later, that wallet is identified as a **Convergence Point**.
* **Why It Matters:** It proves to police that these were not random, isolated frauds, but rather a **single coordinated organized crime syndicate**.

### 4.3 What are Clusters and Clustering Heuristics?
Clustering is the process of grouping multiple distinct wallet addresses together because evidence proves they are controlled by the **same human or organization**.
1. **Common-Input-Ownership (Bitcoin):**
   * On Bitcoin, transactions can combine multiple input addresses into one transfer.
   * To combine them, the sender must possess the private keys to **all** of those input wallets at the same moment.
   * Therefore, every address spent as an input in that transaction shares the same owner.
2. **Shared-Funder Fan-Out:**
   * When one central wallet sends seed money to 10 brand-new wallets simultaneously, those recipient wallets are usually mule accounts operated by the same criminal network.

---

## 5. Real Data vs Mock Data: Where Does LedgerLens Get Its Data?

### 5.1 Is the Blockchain Data Real or Fake?
**The blockchain transaction data is 100% REAL live on-chain data.**
LedgerLens does not simulate transactions. When you submit an address:
* For **Bitcoin**, it queries the live public **Blockstream Esplora API**.
* For **Ethereum**, it queries the live public **Etherscan API**.
* For **Binance Smart Chain**, it queries the live public **BscScan API**.
* For **Polygon**, it queries the live public **PolygonScan API**.
Every block height, transaction hash, timestamp, transferred amount, and recipient wallet is queried directly from the real worldwide blockchain.

### 5.2 What Parts are Seeded or Simulated?
1. **Curated Exchange Labels (`seed_labels.json`):**
   * Real public blockchain intelligence (e.g. from Etherscan, BitInfoCharts, WalletLabels) identifying verified exchange hot/deposit wallets and mixer contracts.
2. **Simulated Government Integrations (`mock_ncrp`, `mock_lea`):**
   * In a hackathon or lab environment, live connections to internal police intranets (NCRP, SAHYOG) cannot be made without government clearances. LedgerLens includes clearly marked simulated connectors demonstrating how the system interfaces with national cybercrime portals in production.
