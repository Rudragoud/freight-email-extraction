"""Accuracy evaluation script for freight email extraction."""

import json
from typing import Dict, List, Any, Tuple


def load_json(filepath: str) -> List[Dict[str, Any]]:
    """Load JSON file."""
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)


def compare_values(predicted: Any, truth: Any, field_name: str) -> bool:
    """
    Compare predicted vs ground truth with type-specific logic.
    
    Args:
        predicted: Predicted value
        truth: Ground truth value
        field_name: Field name for logging
        
    Returns:
        True if values match according to comparison rules
    """
    # Both None/null
    if predicted is None and truth is None:
        return True
    
    # One is None
    if predicted is None or truth is None:
        return False
    
    # Float comparison (2 decimal precision)
    if isinstance(truth, (int, float)) and isinstance(predicted, (int, float)):
        return round(float(predicted), 2) == round(float(truth), 2)
    
    # String comparison (case-insensitive, whitespace trimmed)
    if isinstance(truth, str) and isinstance(predicted, str):
        return predicted.strip().lower() == truth.strip().lower()
    
    # Boolean comparison
    if isinstance(truth, bool) and isinstance(predicted, bool):
        return predicted == truth
    
    # Default: exact match
    return predicted == truth


def evaluate_extraction(
    predictions: List[Dict], 
    ground_truth: List[Dict]
) -> Tuple[Dict[str, float], Dict[str, int], Dict[str, int], List[Dict]]:
    """
    Calculate accuracy metrics for extraction.
    
    Args:
        predictions: List of predicted extractions
        ground_truth: List of ground truth extractions
        
    Returns:
        Tuple of (accuracies_dict, field_correct_dict, field_total_dict, error_details)
    """
    # Fields to evaluate (9 fields, excluding 'id')
    fields = [
        "product_line",
        "origin_port_code",
        "origin_port_name",
        "destination_port_code",
        "destination_port_name",
        "incoterm",
        "cargo_weight_kg",
        "cargo_cbm",
        "is_dangerous"
    ]
    
    # Initialize counters
    field_correct = {field: 0 for field in fields}
    field_total = {field: 0 for field in fields}
    error_details = []
    
    # Create lookup for predictions by email ID
    pred_lookup = {p["id"]: p for p in predictions}
    
    # Compare each email
    for truth in ground_truth:
        email_id = truth["id"]
        pred = pred_lookup.get(email_id)
        
        if not pred:
            print(f"⚠ Warning: Missing prediction for {email_id}")
            for field in fields:
                field_total[field] += 1
            continue
        
        # Compare each field
        for field in fields:
            field_total[field] += 1
            pred_value = pred.get(field)
            truth_value = truth.get(field)
            
            if compare_values(pred_value, truth_value, field):
                field_correct[field] += 1
            else:
                # Track error for analysis
                error_details.append({
                    "email_id": email_id,
                    "field": field,
                    "predicted": pred_value,
                    "truth": truth_value
                })
    
    # Calculate accuracies
    accuracies = {}
    for field in fields:
        if field_total[field] > 0:
            accuracies[field] = (field_correct[field] / field_total[field]) * 100
        else:
            accuracies[field] = 0.0
    
    # Overall accuracy
    total_correct = sum(field_correct.values())
    total_fields = sum(field_total.values())
    accuracies["overall"] = (total_correct / total_fields) * 100 if total_fields > 0 else 0.0
    
    return accuracies, field_correct, field_total, error_details


def print_metrics(
    accuracies: Dict[str, float], 
    field_correct: Dict[str, int], 
    field_total: Dict[str, int]
):
    """Print accuracy metrics in readable format."""
    print("\n" + "="*70)
    print(" "*20 + "EXTRACTION ACCURACY METRICS")
    print("="*70)
    
    # Field-level metrics
    for field, accuracy in accuracies.items():
        if field == "overall":
            continue
        correct = field_correct.get(field, 0)
        total = field_total.get(field, 0)
        status = "✓" if accuracy >= 85 else "✗" if accuracy < 70 else "~"
        print(f"{status} {field:28s}: {accuracy:6.2f}%  ({correct}/{total})")
    
    print("-"*70)
    
    # Overall accuracy with rating
    overall = accuracies["overall"]
    if overall >= 90:
        rating = "EXCEPTIONAL ⭐⭐⭐"
        emoji = "🎉"
    elif overall >= 80:
        rating = "STRONG ⭐⭐"
        emoji = "👍"
    elif overall >= 70:
        rating = "ACCEPTABLE ⭐"
        emoji = "👌"
    else:
        rating = "NEEDS IMPROVEMENT"
        emoji = "⚠️"
    
    print(f"{'OVERALL ACCURACY':28s}: {overall:6.2f}%  {emoji}")
    print(f"{'RATING':28s}: {rating}")
    print("="*70 + "\n")


def print_top_errors(error_details: List[Dict], top_n: int = 10):
    """Print most common errors for debugging."""
    if not error_details:
        print("✓ No errors found!\n")
        return
    
    print("\n" + "="*70)
    print(f"TOP {top_n} ERRORS (for debugging)")
    print("="*70)
    
    for idx, error in enumerate(error_details[:top_n], 1):
        print(f"\n{idx}. Email: {error['email_id']} | Field: {error['field']}")
        print(f"   Predicted: {error['predicted']}")
        print(f"   Truth:     {error['truth']}")
    
    print("\n" + "="*70 + "\n")


def main():
    """Run evaluation."""
    try:
        # Load data
        print("Loading evaluation data...")
        predictions = load_json("output.json")
        ground_truth = load_json("ground_truth.json")
        
        print(f"Loaded {len(predictions)} predictions")
        print(f"Loaded {len(ground_truth)} ground truth entries")
        
        # Evaluate
        accuracies, field_correct, field_total, error_details = evaluate_extraction(
            predictions, 
            ground_truth
        )
        
        # Print results
        print_metrics(accuracies, field_correct, field_total)
        
        # Print top errors for debugging
        if error_details:
            print_top_errors(error_details, top_n=10)
            print(f"Total errors: {len(error_details)}")
        
    except FileNotFoundError as e:
        print(f"\n✗ Error: {e}")
        print("Make sure output.json and ground_truth.json exist in current directory.\n")
    except Exception as e:
        print(f"\n✗ Unexpected error: {e}\n")


if __name__ == "__main__":
    main()
