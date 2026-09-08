# Sample FIRs for document intake

Two complaints for demonstrating **Smart Intake** on the New Trace screen.
Both name the same suspect wallet, which is what lets them also demonstrate
cross-case convergence: two unrelated victims, two states, one wallet.

| File | Format | Complaint | Amount |
|---|---|---|---|
| `FIR-0147-2026-Cyber-Crime-Bengaluru.pdf` | PDF | NCRP/2026/KA/0004471 | Rs. 47,50,000 |
| `FIR-0148-2026-Cyber-Crime-Hyderabad.docx` | Word | NCRP/2026/TS/0009312 | Rs. 22,00,000 |

Suspect wallet in both: `1CRLGcaXajtWVF5EopZgQUqE12dKn8Rtuh`

## Using them

1. Open **New trace** → **Upload FIR document**
2. Pick either file. The wallet, complaint reference and narrative fill in
   automatically, and the extracted text stays visible so you can check what
   the system actually read.
3. Set the hop limit to 1 or 2 and **Start Multi-Hop Trace**.

The two formats exercise different code paths on purpose: the PDF goes
through a text-layer extractor, the Word file through paragraph *and table*
reads. FIR forms are overwhelmingly tables, so the `.docx` is built as
tables - a paragraph-only reader returns almost nothing from it.

A scanned FIR has no text layer and will be refused with a message saying
so, rather than reported as a complaint containing no wallets. Those are
different findings and only one of them means the document was empty.

## Regenerating

Edit the scripts rather than the documents. The suspect wallet appears in
several places in each file, and a document whose narrative names one
address while its data section names another is exactly the inconsistency
the extractor would surface at the worst possible moment.

```
backend/.venv/bin/python fir/generate_fir.py        # the PDF
backend/.venv/bin/python fir/generate_fir_docx.py   # the Word file
```
