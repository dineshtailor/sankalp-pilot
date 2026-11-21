# Industry and regulatory research notes (Project Sankalp)

Read 19 Nov 2026. Where a primary (government) source was found it is listed first; secondary sources are marked.
Every item says how it changes the pilot or the reasoning.

## How the Indian trade channel works (glossary used in the notes)
| Term | Meaning | Where it matters |
|---|---|---|
| C&F / CFA | Carrying & forwarding agent: holds company stock (title stays with the company), bills stockists in the company's name, takes back claims | Doc 3; claims at the billing C&F only (§5.1) |
| Stockist / sub-stockist | Wholesaler (Form 20B/21B licence) buying from the C&F; sub-stockists buy from stockists | §8.3: credit only to the invoiced stockist (EML Agartala case) |
| Primary vs secondary sales | Company → stockist (visible) vs stockist → chemist (not visible, no SSS since DMS pilot stopped) | Why §4.5 stock-norm cannot be enforced; why stuffing is invisible |
| PTS / PTR / MRP | Price to stockist / to retailer / max retail price; PTS = PTR/1.10, PTR = (MRP ex-GST)/1.20 (Annex A) | All claim values at PTS (§5.7) |
| FOC scheme (10+2) | Free goods on a minimum order; quarter-end schemes billed in the last 7–10 days | P2: pull-forward and expiry |
| NE / expiry claim, BED, LBE | Near-expiry, breakage/expiry/damage, loss-before-expiry claims returned by stockists for credit | Claims checker |
| CN | Credit note: a GST document that must reference the original supply | GST time limit below |
| FEFO / RSL | First-expiry-first-out picking; remaining shelf life at dispatch (≥60% in §7.1) | P4 Kolkata |
| DPCO / NLEM / NPPA | Drug price control order 2013 / National List of Essential Medicines 2022 / National Pharmaceutical Pricing Authority | Annual MRP revision |
| SSS | Secondary sales statement from stockists | Missing data |

## Verified references
1. **CGST Act 2017, s.34(2): credit notes.** Finance Act 2022 substituted "the thirtieth day of November" for "September": a GST credit note for a supply must be declared by 30 Nov following the FY of supply (or the annual-return date, if earlier). In force 01-Oct-2022 (Notification 18/2022-Central Tax, 28-Sep-2022). Sources: [CBIC tax information portal, s.34](https://taxinformation.cbic.gov.in/content/html/tax_repository/gst/acts/2017_CGST_act/active/chapter7/section34_v1.00.html); [Finance Act 2022 text (GST Council)](https://gstcouncil.gov.in/sites/default/files/2024-04/finance_act_of_2022.pdf); [PIB press release](https://www.pib.gov.in/PressReleasePage.aspx?PRID=1865179). **Pilot impact:** new INFO check `gst_cn` tells Finance when the supplying invoice is past the GST credit-note deadline (common for near-expiry claims on 18–24-month-old supplies).
2. **DPCO 2013 para 16(2): annual WPI revision.** NPPA order of 25-Mar-2026 allows MRP of scheduled formulations to rise by the WPI change for calendar 2025 over 2024 (0.64956%), effective 01-Apr-2026; non-scheduled under para 20. Secondary sources: [Medical Dialogues](https://medicaldialogues.in/news/industry/pharma/nppa-revises-ceiling-prices-of-138-essential-drugs-with-wpi-linked-hike-effective-april-1-167836), [Outlook](https://www.outlookindia.com/healthcare-spotlight/nppa-permits-064-price-rise-on-essential-medicines-in-line-with-wpi); confirm the order on nppaindia.nic.in before quoting. **Impact:** matches Doc 5 (17-Aug Regulatory Affairs); price change is small, so revaluation of claims at the claim-date PTS (§5.7) is not a material driver. No relabelling and no take-back (CO-POL-014 §6.3), so MRP queries are routed, not claimed.
3. **Trade practice on expiry returns (AIOCD).** AIOCD has pressed companies since 2021 for uniform settlement of leakage, breakage and expiry claims by credit note (Jan-2021 letter), and reported a 2025 circular on LBE claims. Secondary: [Medical Dialogues 2021](https://medicaldialogues.in/news/industry/pharma/aiocd-calls-out-unethical-policies-by-pharma-cos-asks-distribution-heads-to-clean-up-policies-73875); [Business Standard 2017](https://www.business-standard.com/article/companies/chemists-lock-horns-with-abbott-over-expired-drugs-117041201403_1.html). **Impact:** explains why the company cannot simply refuse expiry returns: the lever is upstream (don't push lots that will come back), which is Module C.
4. **CDSCO Good Distribution Practices** (draft guidance): FEFO, records, returns handling. [CDSCO GDP](https://cdsco.gov.in/opencms/export/sites/CDSCO_WEB/Pdf-documents/New-Drugs/GDP.pdf). **Impact:** supports the FEFO root-cause ask (P4).
5. **Drugs Rules 1945:** Forms 20B/21B wholesale licences; Rule 65 records; Schedule H1 register. Referenced, not used in a rule (CO-POL-014 §8.2 blocks billing in SAP on a lapsed licence; the extract has no licence-expiry field).

## Not verified / out of scope
- Vendor claim "30% forecast accuracy in 90 days" (Doc 5): no evidence offered.
- Exact AIOCD LBE settlement formula in the 2025 circular: headline only; not used.
