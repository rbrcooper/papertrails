import sys
import os
import json
from typing import List, Dict, Any

# Add parent directory to path to import modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from processes.utils.bank_standardizer import BankStandardizer

def demonstrate_standardizer():
    """
    Demonstrate how to use the BankStandardizer utility in a real workflow.
    """
    print("Bank Name Standardization Example")
    print("-" * 40)
    
    # Initialize the standardizer
    standardizer = BankStandardizer()
    
    # Example list of raw bank names from extracted data
    raw_bank_names = [
        "Deutsche Bank A.G.",
        "Deutsche Bank Securities Inc.",
        "J.P. Morgan Securities plc",
        "JPMorgan Chase & Co",
        "JPMorgan",
        "BNP Paribas S.A.",
        "BNP PARIBAS",
        "Bank of America Securities",
        "BoFA MERRILL LYNCH",
        "Citibank, N.A.",
        "Citigroup Global Markets Limited",
        "Goldman Sachs International",
        "The Goldman Sachs Group Inc.",
        "Barclays Bank PLC",
        "Barclays Capital"
    ]
    
    # Standardize each bank name
    print("\nStandardizing bank names:")
    print(f"{'Raw Name':<35} | {'Standardized Name':<20} | {'Confidence':<10}")
    print("-" * 70)
    
    standardized_banks = []
    
    for raw_name in raw_bank_names:
        result = standardizer.standardize(raw_name)
        
        if result:
            standard_name, confidence = result
            standardized_banks.append({
                'raw_name': raw_name,
                'standard_name': standard_name,
                'confidence': confidence
            })
            print(f"{raw_name:<35} | {standard_name:<20} | {confidence:.2f}")
        else:
            standardized_banks.append({
                'raw_name': raw_name,
                'standard_name': None,
                'confidence': None
            })
            print(f"{raw_name:<35} | {'Not matched':<20} | {'':<10}")
    
    # Demonstrate adding a new bank
    print("\nAdding a new bank to the standardizer:")
    standardizer.add_bank(
        key="credit agricole",
        standard_name="Credit Agricole",
        aliases=["credit agricole", "crédit agricole", "ca-cib", "credit agricole corporate & investment bank"],
        country="France",
        save=False  # Don't save to the file in this example
    )
    
    # Test with the newly added bank
    new_bank = "Crédit Agricole CIB"
    result = standardizer.standardize(new_bank)
    
    if result:
        standard_name, confidence = result
        print(f"{new_bank:<35} | {standard_name:<20} | {confidence:.2f}")
    else:
        print(f"{new_bank:<35} | {'Not matched':<20} | {'':<10}")
    
    # Demonstrate building a dictionary from raw names
    print("\nBuilding a bank dictionary from raw names:")
    unique_raw_names = [bank['raw_name'] for bank in standardized_banks]
    bank_dict = standardizer.build_bank_dictionary(unique_raw_names)
    
    print(f"Generated {len(bank_dict)} bank entries from {len(unique_raw_names)} raw names")
    
    # Print a sample of the generated dictionary
    print("\nSample entries from generated dictionary:")
    count = 0
    for key, value in bank_dict.items():
        if count >= 3:  # Show just a few examples
            break
        print(f"Key: {key}")
        print(f"  Standard Name: {value['standard_name']}")
        print(f"  Aliases: {', '.join(value['aliases'])}")
        print()
        count += 1

if __name__ == "__main__":
    # Ensure the examples directory exists
    os.makedirs(os.path.dirname(os.path.abspath(__file__)), exist_ok=True)
    
    # Run the demonstration
    demonstrate_standardizer() 