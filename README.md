# Freight Email Extraction System

## Overview

This project implements an **LLM-based email extraction system** to convert unstructured freight pricing enquiry emails into structured shipment data, strictly following the business rules provided in the Task Harmony assessment.

The system processes the given 50 emails, extracts shipment details, and evaluates accuracy against the provided ground truth.

---

## Extracted Fields

For each email, the following fields are extracted:

- `product_line`
- `origin_port_code`, `origin_port_name`
- `destination_port_code`, `destination_port_name`
- `incoterm`
- `cargo_weight_kg`
- `cargo_cbm`
- `is_dangerous`

All outputs are returned as **raw JSON** and validated using **Pydantic**.

---

## Processing Flow

```
emails_input.json
        ↓
Prompt construction (business rules + port reference)
        ↓
Groq LLM call (temperature = 0)
        ↓
JSON parsing and cleanup
        ↓
Port validation & canonical name fixing
        ↓
Pydantic schema validation
        ↓
output.json
```

---

## Core Extraction Logic

### Product Line
- Determined only using **port codes**
- Destination port starts with `IN` → `pl_sea_import_lcl`
- Origin port starts with `IN` → `pl_sea_export_lcl`

### Ports
- Extracted as **5-letter UN/LOCODE**
- Canonical port names are forced from `port_codes_reference.json`
- Manual overrides are applied where reference data is inconsistent
- If a port is not found → both code and name are set to `null`

### Incoterms
- Extracted and normalized to uppercase
- Defaults to `FOB` if missing or ambiguous
- Body text takes precedence over subject

### Weight & CBM
- Unit conversions handled (lbs → kg, MT → kg)
- Rounded to 2 decimal places
- `TBD`, `N/A`, or not mentioned → `null`
- If multiple shipments exist, only the **first shipment** is extracted

### Dangerous Goods
- Detected using rule-based keywords (DG, UN numbers, IMO, Class X)
- Negations handled (`non-DG`, `non-hazardous`)
- Default value is `false`

---

## Validation

All extracted data is validated using **Pydantic**:
- Ensures correct data types
- Enforces valid port codes and product lines
- Normalizes casing and numeric precision

---

## Error Handling

- Automatic retry for Groq rate limits
- Robust JSON parsing from LLM responses
- Emails are never skipped; failed extractions return `null` fields with ID preserved

---

## Accuracy Evaluation

Accuracy is computed using `evaluate.py`:
- Field-wise comparison with ground truth
- Case-insensitive string matching
- Numeric comparison after rounding
- Overall accuracy calculated across all fields

**Overall accuracy on provided dataset: 80%+**

---

Installation
bash# 1. Clone repository
git clone <your-repo-url>
cd freight-email-extraction

# 2. Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure API key
cp .env.example .env
# Edit .env and add your Groq API key:
# GROQ_API_KEY=your_actual_key_here

## Setup & Usage

```bash


pip install -r requirements.txt
python extract.py     # Generates output.json
python evaluate.py    # Prints accuracy metrics
```

Project Structure
freight-email-extraction/
├── extract.py              # Main extraction pipeline
├── prompts.py              # Prompt engineering with evolution history
├── schema.py               # Pydantic models for validation
├── evaluate.py             # Accuracy calculation script
├── output.json             # Final extraction results (50 emails)
├── requirements.txt        # Python dependencies
├── .env.example            # API key template
├── .gitignore              # Git ignore rules
├── README.md               # This file
│
├── emails_input.json       # Input emails (provided)
├── ground_truth.json       # Expected outputs (provided)
└── port_codes_reference.json  # UN/LOCODE mappings (provided)

---

## Summary

This solution uses a **rule-driven LLM prompt** combined with **strict schema validation** to reliably extract structured freight shipment data from unstructured emails, achieving high accuracy while fully adhering to the assessment business rules.