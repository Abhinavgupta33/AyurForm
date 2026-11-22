# Charaka Samhita Volume I - second-stage quality review

Review date: 2026-11-17  
Source: `D:\Downloads\Charaka-Samhita-Acharya-Charaka.pdf`  
Prior inspection: `docs/source_inspection/charaka_volume1_report.md`

This was a read-only review. No PDF modification, production-database change, ChromaDB write, embedding generation, or RAG-corpus update was performed.

## 1. Seven short pages

The existing PyMuPDF extraction (`ocr="never"`) flagged these pages:

| PDF page | Extracted text | Visual finding | Recommendation |
|---:|---|---|---|
| 4 | `4` | Printed page-number/separator page; no body content | Retain as a page record; exclude from prose chunks |
| 6 | `6` | Printed page-number/separator page; no body content | Retain as a page record; exclude from prose chunks |
| 128 | `128` | Printed page-number/separator page between contents and body | Retain as a page record; exclude from prose chunks |
| 198 | `198` | Printed page-number/separator page before Section 4 contents | Retain as a page record; exclude from prose chunks |
| 439 | `439` | Printed page-number/separator page near treatment subsections | Retain as a page record; exclude from prose chunks |
| 511 | `511\n\nFetal Development` | Deliberate section/subsection title page, not an extraction failure | Retain as heading boundary; exclude from ordinary prose chunks |
| 536 | `536` | Printed page-number/separator page before Section 7 | Retain as a page record; exclude from prose chunks |

None of the seven pages is image-only or blank in the visual sense. They are divider/title pages or page-number-only separators. The recommended action is not deletion: preserve them for PDF traceability, but assign a `page_role` such as `separator` or `heading_page` and do not embed them as independent knowledge passages.

## 2. Representative-page validation

Representative pages were rendered with Poppler and compared with the PyMuPDF text output.

| Page | Visual comparison | Result |
|---:|---|---|
| 1 | Cover/title page | Text order is correct: title, handbook subtitle, volume, editor. Layout styling is not represented by plain extraction, as expected. |
| 10 | Sutra-reference explanation and abbreviation table | Paragraph order is correct. The table is flattened into row-like text, but the visible row order is recoverable. Arrow labels and column relationships are lost. |
| 11 | Section 1 contents | Contents entries are in visual order. Some words are visibly truncated in the source itself (`Qualitie`, `Kaph`), so this is not necessarily an extractor omission. |
| 162 | Body text, sutra markers, chapter transition | Reading order is correct across the page. The chapter heading and bracketed note are preserved. A standalone `#26` marker is present in the source/extraction and needs normalization review. |
| 310 | Body text plus editor notes and list-like material | Paragraph order is usable. Editorial note text is interleaved with source material and must be provenance-labeled. List/table-like content is not structurally represented. |
| 621 | Formulation/paste entries | Reading order is mostly correct, but plus signs and ingredient/application lines are layout-dependent and should be parsed as a formulation structure, not ordinary prose. |

Page boundaries are preserved because every record is emitted with its PDF page number. The extraction does not merge neighboring pages, although downstream chunking can create overlap across page boundaries and must preserve a page list for citations.

### Text and hyphenation observations

- The existing cleaner removes soft hyphens and joins a word split across a line-ending hyphen. This is appropriate for ordinary prose but could alter intentionally hyphenated compounds.
- Paragraph breaks are generally represented as blank lines and follow visual order in the inspected pages.
- Typography and transliteration characters are not uniformly normalized. The source includes curly quotes, em/en dashes, accented transliterations, and occasional source glyph substitutions. Preserve original text and record any normalized form separately.
- Headings are not consistently marked. A heading may be a large-font line, a contents entry, an all-caps working label, or a line embedded in running text.

### Tables and reading order

The page-10 table is visually a three-column grid. Plain extraction emits headings and cells sequentially, so it is readable but not schema-safe. The same issue applies to contents tables, food/quality charts, and formulation lists. A layout-aware pass should capture bounding boxes or explicit rows/columns. Do not treat a successful text extraction as proof that table semantics survived.

## 3. Editorial provenance

The PDF explicitly states that editor comments are printed in italics or inside brackets. Inspection found the following distinguishable categories:

| Category | Evidence pattern | Recommended `provenance_role` |
|---|---|---|
| Translated/source-facing text | Prose or verse-like statement followed by a sutra marker | `source_translation_candidate` |
| Editor explanation | Phrases such as “the editor's interpretation”, modern explanatory glosses, or explanatory parentheses | `editor_commentary` |
| Bracketed editorial note | `[...]`, `[[...]]`, `{...}`, or bracketed additions inside a sentence | `editor_bracket_note` |
| Working annotation | `consider moving`, `to be inserted`, `look up`, `chapter?`, asterisks, all-caps draft headings | `editor_working_note` |
| Reformatted table/chart | Contents, abbreviation tables, food/formulation charts, lists with visual columns | `editor_table_or_chart` |
| Legal/front matter | Disclaimer, usage note, editor contact/provenance statements | `legal_or_front_matter` |
| Cross-reference | “see chapter”, “see section”, page references, or references to another modern book | `editor_cross_reference` |

Unbracketed text is not automatically original source material. For example, page 310 contains an unbracketed list followed by an explicit relocation note; page 621 contains formulation presentation and editorial additions such as `[+ ghee]`. Provenance must therefore be assigned at paragraph or line-group level during human review, not inferred solely from brackets.

## 4. Classical-reference validation

The requested examples were located as follows:

| Original marker | PDF page(s) | Interpretation |
|---|---:|---|
| `Su1#41` | 13 | Sutrasthana, chapter 1, sutra 41 |
| `Vi1#14` | 20 and 282 | Vimanasthana, chapter 1, sutra 14; repeated cross-reference |
| `Ci14#26-29` | 10 | Reference-format example in the editor's explanation, not body evidence by itself |

The prior permissive scan found 1,926 reference-like matches, including repeats, ranges, whitespace variants, and editorial references. This is a candidate count, not a validated citation count.

Recommended metadata shape:

```json
{
  "reference_original": "Ci14#26-29",
  "reference_section": "Ci",
  "reference_chapter": 14,
  "reference_sutra_start": 26,
  "reference_sutra_end": 29,
  "pdf_page_number": 10,
  "reference_role": "editor_example"
}
```

For body passages, `reference_role` should distinguish `body_marker`, `cross_reference`, and `editor_example`. Keep the original marker verbatim, because normalization can otherwise erase meaningful formatting or ranges.

## 5. RAG readiness and chunking recommendation

### Required metadata per reviewed passage

At minimum, retain:

- stable `source_id` and source file hash;
- `pdf_page_number` and validated printed page number, when available;
- `section_name` and abbreviation;
- chapter number/title only after review;
- original and normalized reference fields;
- `provenance_role` and `editorial_confidence`;
- extraction method and review status;
- table/formulation role when applicable.

### Recommended chunking

Chunk within reviewed section/chapter boundaries, not across unrelated headings. Keep paragraph and formulation units intact. For tables and recipes, use structured records or carefully labeled row groups. Include a list of contributing PDF pages in every chunk. Never mix `editor_commentary` into a source-translation chunk without an explicit label.

## Known limitations

- This review used text extraction and representative page rendering, not a 621-page line-by-line scholarly collation.
- The PDF's own editing and formatting decisions cannot establish authenticity, translation provenance, or copyright permission.
- Automatic heading and reference detection will produce false positives in contents pages, examples, and editor notes.
- Printed page numbers and PDF page numbers may differ around front matter and separators.
- Table semantics, italics, font size, and some editorial styling are not retained by the current extraction JSON.

## Final readiness decision

**Not ready for production RAG ingestion.** The digital text is technically extractable and page-traceable, but the source requires rights/provenance confirmation, visual review of tables and separators, paragraph-level editorial labeling, validated reference parsing, and an approved review manifest. Until those controls are completed, this PDF must remain outside ChromaDB and the production corpus.
