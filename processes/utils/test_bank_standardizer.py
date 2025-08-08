import sys
import os
import json
from typing import List, Dict, Any, Tuple

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from processes.utils.bank_standardizer import BankStandardizer

def run_test_cases() -> None:
    """Run test cases for the BankStandardizer class."""
    
    # Initialize the bank standardizer
    standardizer = BankStandardizer()
    
    # Define test cases
    test_cases = [
        ("BNP Paribas Securities", "BNP Paribas", 1.0),
        ("Deutsche", "Deutsche Bank AG", 0.9),
        ("Credit Agricole Corporate and Investment Bank", "Credit Agricole", 1.0),
        ("Societe Generale S.A.", "Societe Generale", 1.0),
        ("UBS Limited", "UBS", 1.0),
        ("HSBC", "HSBC", 1.0),
        ("Banco Santander SA", "Santander", 1.0),
        ("J.P. Morgan", "JPMorgan", 1.0),
        ("Bank of America Merrill Lynch", "Bank of America", 1.0),
        ("goldman", "Goldman Sachs", 1.0),
        ("Morgan Stanley & Co.", "Morgan Stanley", 1.0),
        ("Nomura Securities", "Nomura", 1.0),
        ("Royal Bank of Canada", "RBC", 1.0),
        ("City Bank", None, None),  # Should not match
        ("", None, None),  # Empty string
        ("AB", None, None),  # Too short
    ]
    
    print("Running BankStandardizer test cases...")
    print("-" * 70)
    print(f"{'Input':<40} | {'Expected':<20} | {'Result':<20} | {'Confidence':<10} | {'Status':<10}")
    print("-" * 70)
    
    passed = 0
    failed = 0
    
    for input_name, expected_name, expected_confidence in test_cases:
        result = standardizer.standardize(input_name)
        
        if expected_name is None:
            if result is None:
                status = "PASS"
                passed += 1
            else:
                status = "FAIL"
                failed += 1
            
            print(f"{input_name:<40} | {'None':<20} | {str(result):<20} | {'':<10} | {status:<10}")
        else:
            if result is None:
                status = "FAIL"
                failed += 1
                print(f"{input_name:<40} | {expected_name:<20} | {'None':<20} | {'':<10} | {status:<10}")
            else:
                standard_name, confidence = result
                if standard_name == expected_name and (expected_confidence is None or abs(confidence - expected_confidence) < 0.15):
                    status = "PASS"
                    passed += 1
                else:
                    status = "FAIL"
                    failed += 1
                
                print(f"{input_name:<40} | {expected_name:<20} | {standard_name:<20} | {confidence:.2f} | {status:<10}")
    
    print("-" * 70)
    print(f"Test results: {passed} passed, {failed} failed")
    
    # Test the build_bank_dictionary function
    test_build_dictionary()

def test_build_dictionary() -> None:
    """Test the build_bank_dictionary function."""
    
    print("\nTesting build_bank_dictionary function...")
    
    # Create a sample list of raw bank names
    raw_names = [
        "Credit Agricole",
        "Credit Agricole S.A.",
        "Crédit Agricole Corporate and Investment Bank",
        "CA-CIB",
        "Mizuho Bank",
        "Mizuho Securities",
        "Mizuho Financial Group",
        "SMBC",
        "Sumitomo Mitsui Banking Corporation"
    ]
    
    # Initialize the bank standardizer
    standardizer = BankStandardizer()
    
    # Build a dictionary from the raw names
    bank_dict = standardizer.build_bank_dictionary(raw_names)
    
    print("\nGenerated bank dictionary:")
    print(json.dumps(bank_dict, indent=2))
    
    # Check if we have groups for Credit Agricole and Mizuho
    has_ca = False
    has_mizuho = False
    has_smbc = False
    
    for key, bank_info in bank_dict.items():
        if "credit agricole" in key or "agricole" in key:
            has_ca = True
            print(f"\nCredit Agricole group found with {len(bank_info['aliases'])} aliases")
        
        if "mizuho" in key:
            has_mizuho = True
            print(f"Mizuho group found with {len(bank_info['aliases'])} aliases")
            
        if "sumitomo" in key or "smbc" in key:
            has_smbc = True
            print(f"SMBC group found with {len(bank_info['aliases'])} aliases")
    
    print(f"\nGroups found: Credit Agricole: {has_ca}, Mizuho: {has_mizuho}, SMBC: {has_smbc}")

def main() -> None:
    """Main function."""
    # Run the test cases
    run_test_cases()

if __name__ == "__main__":
    main() 