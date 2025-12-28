"""Pydantic models for freight forwarding email extraction."""

from typing import Optional
from pydantic import BaseModel, Field, field_validator


class ShipmentExtraction(BaseModel):
    """Validated shipment extraction model."""
    
    id: str = Field(..., description="Email identifier")
    product_line: Optional[str] = Field(
        None, 
        description="Product line: pl_sea_import_lcl or pl_sea_export_lcl"
    )
    origin_port_code: Optional[str] = Field(
        None, 
        description="5-letter UN/LOCODE for origin port"
    )
    origin_port_name: Optional[str] = Field(
        None, 
        description="Canonical port name from reference"
    )
    destination_port_code: Optional[str] = Field(
        None, 
        description="5-letter UN/LOCODE for destination port"
    )
    destination_port_name: Optional[str] = Field(
        None, 
        description="Canonical port name from reference"
    )
    incoterm: Optional[str] = Field(
        None, 
        description="Incoterm (FOB, CIF, CFR, EXW, DDP, DAP, FCA, CPT, CIP, DPU)"
    )
    cargo_weight_kg: Optional[float] = Field(
        None, 
        description="Cargo weight in kilograms, rounded to 2 decimals"
    )
    cargo_cbm: Optional[float] = Field(
        None, 
        description="Cargo volume in cubic meters, rounded to 2 decimals"
    )
    is_dangerous: bool = Field(
        False, 
        description="Whether cargo contains dangerous goods"
    )
    
    @field_validator('cargo_weight_kg', 'cargo_cbm')
    @classmethod
    def round_numeric_fields(cls, v):
        """Round numeric values to 2 decimal places."""
        if v is not None:
            return round(float(v), 2)
        return v
    
    @field_validator('incoterm')
    @classmethod
    def normalize_incoterm(cls, v):
        """Normalize incoterm to uppercase."""
        if v:
            return v.strip().upper()
        return v
    
    @field_validator('origin_port_code', 'destination_port_code')
    @classmethod
    def normalize_port_code(cls, v):
        """Normalize port code to uppercase."""
        if v:
            v = v.strip().upper()
            if len(v) != 5 or not v.isalpha():
                raise ValueError(f"Port code must be 5 letters: {v}")
            return v
        return v
    
    @field_validator('product_line')
    @classmethod
    def validate_product_line(cls, v):
        """Validate product line values."""
        if v and v not in ["pl_sea_import_lcl", "pl_sea_export_lcl"]:
            raise ValueError(f"Invalid product_line: {v}")
        return v


class Email(BaseModel):
    """Email input model."""
    id: str
    subject: str
    body: str
