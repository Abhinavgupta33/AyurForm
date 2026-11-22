# Charaka Samhita Volume I - preliminary source inspection

Inspection date: 2026-11-17  
Input: `D:\Downloads\Charaka-Samhita-Acharya-Charaka.pdf`  
Status: inspection only. No extraction output, embedding, ChromaDB write, review approval, or production-corpus change was performed.

## Executive finding

This is an edited English handbook/working text, not an authenticated critical edition or an unmodified classical translation. The PDF contains explicit editor notes, bracketed commentary, relocation instructions, draft editorial questions, and cross-reference annotations. It must not be indexed as source-authoritative material without documented permission, editorial separation, and human review.

## PDF metadata

| Field | Observed value |
|---|---|
| PDF format | PDF 1.3 |
| PDF title | Microsoft Word - charakapublish2003.2.volumeI.wrd.doc |
| Author metadata | Connie Reavis |
| Producer | Acrobat Distiller 5.0.5 (Windows) |
| Creation date | 2003-09-15T18:04:10Z (PDF metadata representation) |
| Modification date | 2003-09-15T14:07:05-04:00 (PDF metadata representation) |
| Encryption | None reported |
| Page count | 621 |

The visible text identifies the work as **Charaka Samhita: Handbook on Ayurveda, Volume I**, edited by Gabriel Van Loon. These visible credits are observations, not a rights or authenticity determination.

## Extraction quality

Extraction used the existing `ingestion.extract_text.extract_pdf` function with `ocr="never"` (PyMuPDF digital text path). No OCR was needed or attempted.

| Metric | Result |
|---|---:|
| Pages processed | 621 / 621 |
| Digital-text pages | 621 |
| OCR pages | 0 |
| Blank pages | 0 |
| Extracted characters | 1,053,042 |
| Pages with at least 40 characters | 614 |
| Usable-page proportion (40-character threshold) | 98.87% |

The pipeline produced no page-level OCR or open-PDF errors. “Usable” here only means enough extracted characters for downstream inspection; it does not mean the text is editorially clean or suitable for indexing.

### Short or unusual pages

The extractor flagged these pages as unusually short:

| Page | Characters | Interpretation for review |
|---:|---:|---|
| 4 | 1 | Printed page-number-only page or separator |
| 6 | 1 | Printed page-number-only page or separator |
| 128 | 3 | Printed page-number-only/separator-like page |
| 198 | 3 | Printed page-number-only/separator-like page |
| 439 | 3 | Printed page-number-only/separator-like page |
| 511 | 22 | Heading-only page: “Fetal Development” |
| 536 | 3 | Printed page-number-only/separator-like page |

Additional pages below 200 characters are mainly tables of contents or section index pages (for example pages 1, 93, 129, 199, 234, 283, 375, 469, and 587). They should be retained as page records but treated as navigational/editorial matter rather than ordinary prose passages.

No pages were classified as blank. No pages were classified as garbled by the extraction function. Manual review is still required for typographic substitution artifacts (curly quotes, dashes, accented transliterations, and occasional visibly corrupted glyphs in the source text).

## Chapter and section boundaries

The volume's table of contents gives these major boundaries:

| Section | Title | Starting page |
|---:|---|---:|
| 1 | Principles | 11 |
| 2 | Study | 101 |
| 3 | Diagnosis | 129 |
| 4 | Healthy Living | 199 |
| 5 | Treatment Procedures | 291 |
| 6 | Fertility | 469 |
| 7 | Formulation | 537 |
| 8 | Specific Diseases | 629 (listed as Volume II; outside this PDF) |

The PDF itself explains the classical section abbreviations and chapter counts on page 10: Sutrasthana (`Su`, 30 chapters), Nidanasthana (`Ni`, 8 chapters in the printed explanatory table), Vimanasthana (`Vi`, 8), Sarirasthana (`Sa`, 8), Indriyasthana (`In`, 12), Cikitsisthana (`Ci`, 30), Kalpasthana (`Ka`, 12), and Siddhisthana (`Si`, 12). The wording and counts should be verified against the intended authorized source before being used as metadata.

Section heading pages observed by extraction: 11, 101, 129, 199, 291, 469, and 537. Within sections, chapter and subsection headings are often embedded in running text, with inconsistent capitalization and editorial labels; automatic heading detection alone is not reliable.

## Classical reference markers

The extraction contains many references in the expected section/chapter/sutra style. Examples confirmed in the text include:

- `Su1#41` (page 13)
- `Su1#42`, `Su1#43`, `Su30#21` (pages 13-14)
- `Vi1#14` (present in the extracted reference set; page location must be checked in the review manifest before indexing)
- `Ci14#26-29` (page 10's reference-format example)
- `Su25#29`, `Su9#3`, `Su30#20`, `Vi3#24`, `Su11#39`, and many additional occurrences

The inspection found 1,926 reference-like matches using a permissive pattern. This includes repeated references, ranges, whitespace variants (`Ci 14 #26`), and editorial cross-references. A future parser must normalize format while preserving the original marker and page location, and must not assume every marker is a source verse citation.

## Page numbers and traceability

Page numbers can be preserved reliably at the PDF-record level: every extracted page has its 1-based PDF page number. Printed page numbers also appear in the extracted text on most pages, but front matter, contents pages, and separator pages create offsets. Any ingestion record should retain both:

- `pdf_page_number` (stable physical PDF page index), and
- `printed_page_number` (only when explicitly detected and validated).

Chapter, section, and sutra markers can be retained as candidate metadata, but many are editorial references rather than the passage's own heading. No verse-number field should be inferred when the text does not provide a clear marker.

## Tables and layout-sensitive material

The PDF contains table-like material that ordinary line extraction flattens, including:

- the page-5 volume/section table of contents;
- the page-10 section-abbreviation and chapter-count table;
- section-level contents pages (for example pages 11, 101, 129, 199, 291, 469, and 537);
- charts of qualities, tastes, foods, formulations, and dosage/material lists throughout the volume.

The lightweight inspection heuristic did not identify pipe-delimited tables, so `possible_tables=0` from that heuristic must not be interpreted as “no tables.” Table boundaries require visual review or a layout-aware extraction pass. Tables should be stored separately or represented with explicit row/column structure rather than embedded as ordinary prose chunks.

## Editorial and non-source material

The PDF explicitly states that editor comments are printed in italics or inside brackets (page 9). The inspection found numerous examples of material that must be separated from a translated source passage:

- legal/editorial notices (including the editor's medical disclaimer on page 2);
- bracketed explanations and interpretation, e.g. `[the editor's interpretation here is that ...]`;
- working notes such as `*is there more info @ blood?*`, `consider moving`, `to be inserted`, `look up the intent`, and `chapter?`;
- relocation and assembly directions such as `[Consider moving to appropriate section ...]`;
- draft annotations using braces, double brackets, asterisks, and all-caps working headings;
- section summaries and table-of-contents material that describe the editor's organization rather than a translated verse;
- modern explanatory language and references to other books/editors.

These markers occur across the body, not only in the front matter. The text should therefore be modeled with an explicit provenance/role field (for example `source_translation`, `editor_commentary`, `editor_working_note`, `table_of_contents`, `legal_notice`) before any retrieval use.

## Rights, authenticity, and ingestion decision

No copyright license, authorization record, translator agreement, or provenance certificate was supplied with the PDF. The file must remain outside the production corpus until the user provides an authorized-use basis and approves a review manifest. The visible “edited handbook” presentation and extensive editorial intervention mean it should not be represented to users as an original Charaka Samhita text.

**Decision: do not ingest, embed, or index this PDF at this stage.** The next safe step is a human review workflow that (1) verifies rights and provenance, (2) visually checks all short pages and tables, (3) labels source text versus editorial matter, (4) validates section/chapter/sutra parsing, and (5) records an explicit approval manifest before chunking or embedding.

## Reproducibility note

The report was generated by calling the existing PyMuPDF extraction function directly with OCR disabled. No files under the configured extraction, metadata, vector-store, or production database locations were written. The original PDF was not modified.
