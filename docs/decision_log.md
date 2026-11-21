# Decision log

| # | Date | Decision | Why (evidence) | Alternatives rejected |
|---|---|---|---|---|
| D1 | 19-Nov-26 | Do **not** build the AI demand-forecasting tool the CFO asked for | Partial-fill rate holds steady at 92-93%; the fill-rate fall comes from lines not supplied at all. Lucknow at 0.24 months of cover while Kolkata sits at 3.5-6.5 (cnf_stock_snapshot). 95% of expiry claims are on the 15 scheme SKUs; scheme lots come back at 3-9% vs 1-8% without scheme. A forecast cannot fix "where" stock goes or a sales push | Vendor demand-sensing pilot (₹ unknown, 12 months) |
| D2 | 19-Nov-26 | Primary user = claims executive in Commercial Finance | Money that leaves the company today: duplicates, late and over-quantity claims credited (₹21.1 lakh in the last 12 months, each claim counted once). Neha: "Something that checks a claim before it reaches my team" | Chatbot over the data (no user, no decision) |
| D3 | 19-Nov-26 | Rules in Python, model only reads emails and writes notes | Brief: "if a formula can do it, the model should not". A credit note is a GST document | Letting the model judge claims |
| D4 | 19-Nov-26 | Model note is discarded if it contains any number not in the evidence | Accuracy bar rule 2 (nothing invented) | Trusting the prompt alone |
| D5 | 19-Nov-26 | Regex fallback reader, so the app works with no key or when the model fails | Deployment risk; the panel demo must not depend on a third-party API | Hard failure without a key |
| D6 | 19-Nov-26 | Stockist-level stock-norm screen (§4.5) replaced by an SKU-level circular check | Backtest of the per-stockist estimate flagged 1% of pairs and caught 1.8% of later claims. Stuffing is uniform across stockists and differs by SKU | Shipping a screen that does not discriminate |
| D7 | 21-Nov-26 (revised) | Add a stranded-lot list to Stock rebalance | The 19-Nov projection assumed FEFO picking and showed no C&F risk. The Hooghly voice note challenged that: the data shows 7 idle lots worth ₹11.8 lakh, at Kolkata only | Keeping the FEFO-based projection |
| D11 | 21-Nov-26 | Report free goods below the 1.5x minimum on the most lenient reading (₹1.05 cr), outside the savings total | Measurement is a client question; it overlaps the FOC-cap saving | Adding it to the savings headline |
| D12 | 21-Nov-26 | Transcribe voice notes with Gemini 2.5 Pro via OpenRouter, with the user's approval | Local Whisper is blocked by Windows Application Control. Each spoken claim is tested in the data | Quoting transcripts as fact |
| D13 | 21-Nov-26 | Report ₹1.70 cr as savings: ₹1.02 cr refunds + ₹68.3 lakh free goods at PTS | Free goods are valued at selling price and making cost is not in the pack, so calling all of it cash would overstate it | Keeping the single 'cash' label |
| D8 | 19-Nov-26 | `row` = spreadsheet row (header = 1) | An auditor opens the CSV in Excel and goes straight to the row | Zero-based index |
| D9 | 19-Nov-26 | Parallel check nodes (window, quantity, duplicate, invoice) | Independent checks, one state key each (brief's design table); easy to add a check | One monolithic node |
| D10 | 19-Nov-26 | No interrupt()/checkpointer | The person acts outside the tool (SAP CN). The pilot is read-only, so there is nothing to resume | Human-in-loop pause inside the graph |
