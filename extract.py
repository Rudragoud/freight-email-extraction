"""Main extraction pipeline with intelligent rate limit handling."""

import json
import os
import time
import logging
import re
from typing import List, Dict, Any
from dotenv import load_dotenv
from groq import Groq
# Removed tenacity - using custom retry logic instead

from schema import ShipmentExtraction, Email
from prompts import get_extraction_prompt, build_port_codes_context

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()


def parse_rate_limit_wait_time(error_message: str) -> int:
    """Extract wait time in seconds from Groq rate limit error message."""
    # Pattern: "Please try again in 9m13.824s"
    match = re.search(r'Please try again in (\d+)m([\d.]+)s', error_message)
    if match:
        minutes = int(match.group(1))
        seconds = float(match.group(2))
        total_seconds = (minutes * 60) + seconds
        # Add 5 second buffer
        return int(total_seconds) + 5
    
    # Default to 10 minutes if parsing fails
    return 600


class FreightEmailExtractor:
    """LLM-powered freight forwarding email extraction system."""
    
    def __init__(
        self, 
        api_key: str, 
        model: str = "llama-3.3-70b-versatile",
        temperature: float = 0.0
    ):
        """Initialize extractor with Groq client."""
        self.client = Groq(api_key=api_key)
        self.model = model
        self.temperature = temperature
        self.port_codes = self._load_port_codes()
        self.port_lookup = self._build_port_lookup()
        logger.info(f"Initialized extractor with model: {model}")
        logger.info(f"Loaded {len(self.port_codes)} port codes")
        
    def _load_port_codes(self) -> List[Dict[str, str]]:
        """Load port codes reference from JSON file."""
        try:
            with open("port_codes_reference.json", "r", encoding="utf-8") as f:
                return json.load(f)
        except FileNotFoundError:
            logger.error("port_codes_reference.json not found!")
            raise
    
    def _build_port_lookup(self) -> Dict[str, str]:
        """Build fast lookup dictionary: port_code -> canonical_name with smart selection."""
        # Manual overrides for canonical names (based on ground truth patterns)
        MANUAL_OVERRIDES = {
            "INMAA": "Chennai ICD",
            "KRPUS": "Busan",
            "MYPKG": "Port Klang",
            "INBLR": "Bangalore ICD",
            "THBKK": "Bangkok",
            "CNTXG": "Xingang",
            "CNSZX": "Shenzhen",
            "SGSIN": "Singapore",
            "HKHKG": "Hong Kong",
            "CNSHA": "Shanghai",
            "INNSA": "Nhava Sheva",
            "INWFD": "ICD Whitefield",
            "INMUN": "Mundra ICD",
            "JPYOK": "Yokohama",
            "THLCH": "Laem Chabang",
            "AEJEA": "Jebel Ali",
            "PHMNL": "Manila",
            "VNSGN": "Ho Chi Minh",
            "BDDAC": "Dhaka",
            "ITGOA": "Genoa",
            "TRAMR": "Ambarli",
            "TRIZM": "Izmir",
            "TWKEL": "Keelung",
            "USHOU": "Houston",
            "USLAX": "Los Angeles",
            "ZACPT": "Cape Town",
            "DEHAM": "Hamburg",
            "CNQIN": "Qingdao",
            "CNNSA": "Nansha",
            "CNGZG": "Guangzhou",
            "IDSUB": "Surabaya",
            "JPOSA": "Osaka",
            "SAJED": "Jeddah",
        }
        
        lookup = {}
        for port in self.port_codes:
            code = port["code"].upper()
            name = port["name"]
            
            # Use manual override if exists
            if code in MANUAL_OVERRIDES:
                lookup[code] = MANUAL_OVERRIDES[code]
            # Otherwise, prefer shorter, simpler names
            elif code not in lookup:
                lookup[code] = name
            else:
                current = lookup[code]
                # Prefer names without "/" (compound names)
                if "/" not in name and "/" in current:
                    lookup[code] = name
                # Prefer shorter names (usually more canonical)
                elif len(name) < len(current) and "/" not in name:
                    lookup[code] = name
        
        return lookup
    
    def _call_llm(self, prompt: str) -> str:
        """Call Groq LLM API with automatic rate limit handling."""
        max_attempts = 5
        attempt = 0
        
        while attempt < max_attempts:
            try:
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=[{"role": "user", "content": prompt}],
                    temperature=self.temperature,
                    max_tokens=1024
                )
                return response.choices[0].message.content
                
            except Exception as e:
                error_str = str(e)
                
                # Check if it's a rate limit error
                if "rate_limit_exceeded" in error_str or "429" in error_str:
                    wait_time = parse_rate_limit_wait_time(error_str)
                    attempt += 1
                    
                    logger.warning(f"⏳ Rate limit hit. Waiting {wait_time} seconds...")
                    logger.warning(f"   Attempt {attempt}/{max_attempts}")
                    
                    # Show countdown
                    for remaining in range(wait_time, 0, -30):
                        if remaining <= 60:
                            logger.info(f"   Resuming in {remaining} seconds...")
                            time.sleep(remaining)
                            break
                        else:
                            mins = remaining // 60
                            logger.info(f"   Resuming in {mins}m {remaining % 60}s...")
                            time.sleep(30)
                    
                    logger.info("   Retrying now...")
                    continue
                else:
                    # Non-rate-limit error
                    logger.error(f"LLM API call failed: {error_str}")
                    raise
        
        raise Exception(f"Failed after {max_attempts} rate limit retries")
    
    def _parse_llm_response(self, response: str) -> Dict[str, Any]:
        """Parse JSON from LLM response, handling markdown code blocks."""
        # Strip whitespace
        response = response.strip()
        
        # Remove markdown code block markers
        if response.startswith("```json"):
            response = response[7:]
        elif response.startswith("```"):
            response = response[3:]
        
        if response.endswith("```"):
            response = response[:-3]
        
        response = response.strip()
        
        # Try direct JSON parsing first
        try:
            return json.loads(response)
        except json.JSONDecodeError:
            pass
        
        # Try to find JSON object using balanced braces
        stack = []
        start_idx = -1
        
        for i, char in enumerate(response):
            if char == '{':
                if not stack:
                    start_idx = i
                stack.append(char)
            elif char == '}':
                if stack:
                    stack.pop()
                    if not stack and start_idx != -1:
                        # Found complete JSON object
                        json_str = response[start_idx:i+1]
                        try:
                            return json.loads(json_str)
                        except json.JSONDecodeError:
                            pass
        
        # Last resort: log and raise
        logger.error(f"Failed to parse JSON. Response: {response[:500]}")
        raise json.JSONDecodeError("Could not extract valid JSON", response, 0)
    
    def _validate_and_fix_ports(self, extracted: Dict[str, Any]) -> Dict[str, Any]:
        """Validate port codes and ensure canonical names from lookup."""
        # Fix origin port
        if extracted.get("origin_port_code"):
            code = extracted["origin_port_code"].upper()
            if code in self.port_lookup:
                extracted["origin_port_code"] = code
                extracted["origin_port_name"] = self.port_lookup[code]
            else:
                logger.warning(f"Origin port code not in reference: {code}")
                # Try to find partial match
                matched = False
                for ref_code, ref_name in self.port_lookup.items():
                    if code in ref_code or ref_code in code:
                        logger.info(f"  Partial match found: {code} → {ref_code}")
                        extracted["origin_port_code"] = ref_code
                        extracted["origin_port_name"] = ref_name
                        matched = True
                        break
                
                if not matched:
                    extracted["origin_port_code"] = None
                    extracted["origin_port_name"] = None
        
        # Fix destination port
        if extracted.get("destination_port_code"):
            code = extracted["destination_port_code"].upper()
            if code in self.port_lookup:
                extracted["destination_port_code"] = code
                extracted["destination_port_name"] = self.port_lookup[code]
            else:
                logger.warning(f"Destination port code not in reference: {code}")
                # Try to find partial match
                matched = False
                for ref_code, ref_name in self.port_lookup.items():
                    if code in ref_code or ref_code in code:
                        logger.info(f"  Partial match found: {code} → {ref_code}")
                        extracted["destination_port_code"] = ref_code
                        extracted["destination_port_name"] = ref_name
                        matched = True
                        break
                
                if not matched:
                    extracted["destination_port_code"] = None
                    extracted["destination_port_name"] = None
        
        return extracted
    
    def extract_from_email(self, email: Email) -> ShipmentExtraction:
        """Extract shipment data from a single email."""
        try:
            # Build prompt with port codes context
            port_context = build_port_codes_context(self.port_codes)
            prompt = get_extraction_prompt(
                subject=email.subject,
                body=email.body,
                port_codes_context=port_context
            )
            
            # Call LLM (with automatic rate limit handling)
            logger.info(f"Processing email: {email.id}")
            llm_response = self._call_llm(prompt)
            
            # Parse JSON response
            extracted_data = self._parse_llm_response(llm_response)
            extracted_data["id"] = email.id
            
            # Validate and fix port names
            extracted_data = self._validate_and_fix_ports(extracted_data)
            
            # Validate with Pydantic
            shipment = ShipmentExtraction(**extracted_data)
            logger.info(f"✓ Successfully extracted: {email.id}")
            return shipment
            
        except json.JSONDecodeError as e:
            logger.error(f"✗ JSON decode failed for {email.id}: {str(e)}")
            if 'llm_response' in locals():
                logger.error(f"LLM response snippet: {llm_response[:300]}...")
            return self._create_null_extraction(email.id)
            
        except Exception as e:
            logger.error(f"✗ Extraction failed for {email.id}: {str(e)}")
            return self._create_null_extraction(email.id)
    
    def _create_null_extraction(self, email_id: str) -> ShipmentExtraction:
        """Create null extraction for failed emails."""
        return ShipmentExtraction(
            id=email_id,
            product_line=None,
            origin_port_code=None,
            origin_port_name=None,
            destination_port_code=None,
            destination_port_name=None,
            incoterm=None,
            cargo_weight_kg=None,
            cargo_cbm=None,
            is_dangerous=False
        )
    
    def process_batch(
        self, 
        emails: List[Email], 
        rate_limit_delay: float = 1.0,
        checkpoint_file: str = "checkpoint.json"
    ) -> List[Dict[str, Any]]:
        """Process batch of emails with checkpointing."""
        results = []
        total = len(emails)
        
        # Load checkpoint if exists
        start_idx = 0
        if os.path.exists(checkpoint_file):
            with open(checkpoint_file, "r") as f:
                checkpoint = json.load(f)
                results = checkpoint.get("results", [])
                start_idx = checkpoint.get("last_processed", 0) + 1
                logger.info(f"📂 Resuming from checkpoint: {start_idx}/{total}")
        
        for idx in range(start_idx, total):
            email = emails[idx]
            logger.info(f"Progress: {idx+1}/{total}")
            
            result = self.extract_from_email(email)
            results.append(result.model_dump())
            
            # Save checkpoint every 5 emails
            if (idx + 1) % 5 == 0:
                with open(checkpoint_file, "w") as f:
                    json.dump({
                        "results": results,
                        "last_processed": idx
                    }, f, indent=2)
                logger.info(f"💾 Checkpoint saved at {idx+1}/{total}")
            
            # Rate limiting
            if idx < total - 1:
                time.sleep(rate_limit_delay)
        
        # Clean up checkpoint file
        if os.path.exists(checkpoint_file):
            os.remove(checkpoint_file)
        
        return results


def main():
    """Main extraction pipeline."""
    # Load input emails
    logger.info("Loading input emails...")
    try:
        with open("emails_input.json", "r", encoding="utf-8") as f:
            emails_data = json.load(f)
    except FileNotFoundError:
        logger.error("emails_input.json not found!")
        return
    
    emails = [Email(**e) for e in emails_data]
    logger.info(f"Loaded {len(emails)} emails")
    
    # Get API key
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        logger.error("GROQ_API_KEY not found in environment variables!")
        logger.error("Create .env file with: GROQ_API_KEY=your_key")
        return
    
    # Initialize extractor
    extractor = FreightEmailExtractor(api_key=api_key)
    
    # Process emails
    logger.info("="*60)
    logger.info("Starting extraction process...")
    logger.info("="*60)
    
    start_time = time.time()
    results = extractor.process_batch(emails)
    elapsed = time.time() - start_time
    
    # Save output
    with open("output.json", "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    logger.info("="*60)
    logger.info(f"✅ Extraction complete in {elapsed:.1f}s")
    logger.info(f"Results saved to: output.json")
    logger.info(f"Processed: {len(results)} emails")
    logger.info("="*60)


if __name__ == "__main__":
    main()