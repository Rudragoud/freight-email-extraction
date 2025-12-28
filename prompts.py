"""Production-grade prompt with comprehensive business rules and examples."""


def build_port_codes_context(port_codes: list, max_ports: int = 47) -> str:
    """Generate complete port codes reference for LLM context."""
    port_list = "\n".join(
        [f"  {p['code']}: {p['name']}" for p in port_codes[:max_ports]]
    )
    return f"**Port Codes Reference (UN/LOCODE):**\n{port_list}"


# V6: Production prompt with comprehensive rules and examples
PROMPT_V6_PRODUCTION = """You are an expert freight forwarding data extraction system. Extract structured shipment details from the email below following ALL business rules precisely.

**Email Subject:** {subject}
**Email Body:** {body}

{port_codes_context}

**EXTRACTION RULES (FOLLOW EXACTLY):**

**1. Product Line Determination:**
   - STEP 1: First identify origin and destination port codes
   - STEP 2: Check port codes, NOT port names
   - If destination port code starts with "IN" (India) → "pl_sea_import_lcl"
   - If origin port code starts with "IN" (India) → "pl_sea_export_lcl"
   
   Examples:
   - "Bangkok to Chennai" → dest=INMAA (starts with IN) → pl_sea_import_lcl
   - "Chennai to Busan" → origin=INMAA (starts with IN) → pl_sea_export_lcl
   - "Hong Kong to Mumbai" → dest=INNSA (starts with IN) → pl_sea_import_lcl

**2. Port Code & Name Extraction:**
   
   **Port Code Rules:**
   - Must be exact 5-letter UN/LOCODE from reference above
   - Format: 2-letter country + 3-letter location (e.g., INMAA, HKHKG, CNSHA)
   - Use ONLY codes that exist in the reference list
   - If port not in reference → null for both code and name
   
   **Common Abbreviations → Port Code Mapping:**
   - Chennai/MAA/Madras → INMAA
   - Mumbai/Bombay/NSA/Nhava Sheva → INNSA
   - Bangalore/BLR → INBLR
   - Hyderabad/HYD → Use closest match from reference
   - Hong Kong/HK/HKG → HKHKG
   - Shanghai/SHA → CNSHA
   - Shenzhen/SZX → CNSZX
   - Singapore/SIN → SGSIN
   - Busan/PUS → KRPUS
   - Bangkok/BKK → THBKK
   - Jeddah/JED → SAJED
   - Jebel Ali/JBL → AEJEA
   - Xingang/Tianjin/TXG → CNTXG
   - Yokohama/YOK → JPYOK
   - Laem Chabang/LCH → THLCH
   - Port Klang/PKG → MYPKG
   - Manila/MNL → PHMNL
   - Ho Chi Minh/HCM/SGN → VNSGN
   - Ambarli/Istanbul/AMR → TRAMR
   - Izmir/IZM → TRIZM
   - Keelung/KEL → TWKEL
   - Houston/HOU → USHOU
   - Los Angeles/LAX → USLAX
   - Dhaka/DAC → BDDAC
   - Colombo → LKCMB (check reference)
   - Cape Town/CPT → ZACPT
   - Hamburg/HAM → DEHAM
   - Qingdao/QIN → CNQIN
   - Nansha/NSA → CNNSA
   - Guangzhou/GZG → CNGZG
   - Surabaya/SUB → IDSUB
   - Osaka/OSA → JPOSA
   - Genoa/GOA → ITGOA
   - Mundra → INMUN
   - ICD Whitefield → INWFD
   
   **Port Name Rules:**
   - MUST use EXACT canonical name from reference for the matched code
   - Do NOT make up port names - use reference list only
   - If code is found, name MUST be from reference
   - If code is null, name is also null
   
   **Multi-Port Handling:**
   - If "via" or "transshipment" mentioned: Use direct origin→destination, ignore intermediate ports
   - If "ICD" mentioned with main port: The ICD location is usually the final destination
   - Example: "Shanghai to Chennai ICD via Chennai" → origin=CNSHA, dest=INMAA
   - Example: "Chennai to Bangkok ICD via Laem Chabang" → origin=INMAA, dest=THBKK

**3. Incoterms:**
   - Valid incoterms: FOB, CIF, CFR, EXW, DDP, DAP, FCA, CPT, CIP, DPU (case-insensitive)
   - Normalize to UPPERCASE
   - **Default to "FOB" if:**
     * Not mentioned at all
     * Ambiguous (e.g., "FOB or CIF", "FOB/CIF")
     * Multiple incoterms mentioned without clarity
   - **Conflict Resolution:** Body text takes precedence over subject
   
   Examples:
   - Subject: "FOB terms", Body: "requesting CIF rates" → Use CIF (body wins)
   - "FOB or CIF terms" → Use FOB (ambiguous, use default)
   - No mention → Use FOB (default)
   - "FCA terms" → Use FCA (clear and valid)

**4. Cargo Weight (cargo_weight_kg):**
   
   **Unit Conversions:**
   - Pounds (lbs/lb) → kg: multiply by 0.453592
   - Tonnes (MT/tons) → kg: multiply by 1000
   - Already in kg → use as-is
   
   **Rounding:** Always round to 2 decimal places
   
   **Null Handling:**
   - "TBD", "N/A", "to be confirmed", "to be advised" → null
   - Not mentioned → null
   - Explicit zero "0 kg" → 0.00 (NOT null)
   
   **Multiple Shipments:** Extract weight of FIRST shipment only
   
   Examples:
   - "1980 KGS" → 1980.0
   - "500 lbs" → 226.8 (500 × 0.453592)
   - "1.5 MT" → 1500.0 (1.5 × 1000)
   - "850 kg" → 850.0
   - "Weight TBD" → null
   - "0 kg" → 0.0

**5. Cargo Volume (cargo_cbm):**
   
   **Extraction Rules:**
   - Look for CBM, cubic meters, m³, RT (revenue ton = 1 CBM)
   - Round to 2 decimal places
   - "TBD", "N/A", "to be confirmed" → null
   - Not mentioned → null
   - Explicit zero → 0.00 (NOT null)
   
   **DO NOT Calculate:**
   - If only dimensions given (L×W×H), extract as null
   - Do not compute CBM from dimensions
   
   **Multiple Shipments:** Extract CBM of FIRST shipment only
   
   Examples:
   - "3.8 CBM" → 3.8
   - "5 cubic meters" → 5.0
   - "2.4 RT" → 2.4 (RT = revenue ton = 1 CBM)
   - "1.5 m³" → 1.5
   - "Volume TBD" → null
   - "Dimensions 120x80x100 cm" → null (don't calculate)

**6. Dangerous Goods (is_dangerous):**
   
   **True if ANY of these present:**
   - "DG", "dangerous goods", "dangerous cargo"
   - "hazardous", "hazmat"
   - "Class" followed by number (e.g., "Class 3", "Class 9")
   - "IMO", "IMDG"
   - "UN" followed by number (e.g., "UN 1263", "UN 2920")
   - "Flammable", "Corrosive", "Toxic", "Explosive"
   - Specific chemicals with hazard classification
   
   **False if ANY of these present:**
   - "non-hazardous", "non-DG", "non hazardous"
   - "not dangerous", "non dangerous goods"
   
   **Default:** false (if no mention of dangerous goods)
   
   Examples:
   - "Class 3 flammable liquid" → true
   - "UN 1993 paint thinner" → true
   - "non-DG cargo" → false
   - "regular cargo, non-hazardous" → false
   - No mention → false

**7. Conflict Resolution & Edge Cases:**
   
   - **Subject vs Body Conflict:** Body takes precedence (more detailed)
   - **Multiple Shipments in Email:** Extract FIRST shipment only
   - **Multiple Ports Listed:** Use origin→destination pair, ignore transshipment
   - **Port Not in Reference:** Use null for both code and name
   - **Ambiguous Information:** Use most conservative/default value (FOB for incoterm, null for missing data)

**8. Multiple Shipments Example:**
   Email: "Two shipments: 1) Shanghai to Chennai, 500kg, 2.5 CBM; 2) Beijing to Mumbai, 300kg, 1.8 CBM"
   Extract: origin_port_code=CNSHA, destination_port_code=INMAA, cargo_weight_kg=500.0, cargo_cbm=2.5
   (First shipment only)

**9. Transshipment Example:**
   Email: "Hong Kong to ICD Bangalore via Chennai"
   Extract: origin_port_code=HKHKG, destination_port_code=INBLR
   (Direct route, ignore "via Chennai")

**CRITICAL OUTPUT REQUIREMENTS:**
- Return ONLY the raw JSON object
- DO NOT wrap in markdown code blocks (no ```json or ```)
- DO NOT add any explanation or preamble
- DO NOT add comments in JSON
- Use exact field names as specified
- Use null (not "null" string) for missing values
- Use false/true for boolean (not "false"/"true" strings)

**Return this exact JSON structure:**
{{
  "product_line": "pl_sea_import_lcl",
  "origin_port_code": "HKHKG",
  "origin_port_name": "Hong Kong",
  "destination_port_code": "INMAA",
  "destination_port_name": "Chennai ICD",
  "incoterm": "FOB",
  "cargo_weight_kg": 500.0,
  "cargo_cbm": 2.5,
  "is_dangerous": false
}}

**EXTRACT NOW - Return ONLY raw JSON:**"""


def get_extraction_prompt(subject: str, body: str, port_codes_context: str) -> str:
    """Generate extraction prompt with email content and port codes."""
    return PROMPT_V6_PRODUCTION.format(
        subject=subject,
        body=body,
        port_codes_context=port_codes_context
    )


# Current production prompt
CURRENT_PROMPT = PROMPT_V6_PRODUCTION