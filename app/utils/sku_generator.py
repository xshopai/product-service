"""
SKU Generation Utility
Auto-generates unique SKUs based on product attributes
"""

import re
from typing import Optional


def generate_sku(product_name: str, color: Optional[str] = None, size: Optional[str] = None) -> str:
    """
    Generate SKU from product name and variant attributes.
    
    Format: {PRODUCTCODE}-{COLOR}-{SIZE}
    Example: IP15-BLK-128 (iPhone 15, Black, 128GB)
    
    Args:
        product_name: Product name (e.g., "iPhone 15")
        color: Variant color (e.g., "Black")
        size: Variant size (e.g., "128GB")
    
    Returns:
        Generated SKU string
    """
    # Extract product code from name
    # Remove special characters and take initials + numbers
    product_code = _extract_product_code(product_name)
    
    # Process color
    color_code = _extract_attribute_code(color) if color else None
    
    # Process size
    size_code = _extract_attribute_code(size) if size else None
    
    # Build SKU parts
    sku_parts = [product_code]
    if color_code:
        sku_parts.append(color_code)
    if size_code:
        sku_parts.append(size_code)
    
    return "-".join(sku_parts).upper()


def _extract_product_code(product_name: str) -> str:
    """
    Extract product code from product name.
    
    Examples:
        "iPhone 15" -> "IP15"
        "Samsung Galaxy S23" -> "SGS23"
        "Nike Air Max 270" -> "NAM270"
        "T-Shirt Classic" -> "TSC"
    """
    # Remove special characters except spaces and numbers
    cleaned = re.sub(r'[^a-zA-Z0-9\s]', '', product_name)
    
    # Split into words
    words = cleaned.split()
    
    if not words:
        return "PROD"
    
    # Extract initials and numbers
    initials = ""
    numbers = ""
    
    for word in words:
        # Get first letter of each word
        if word and word[0].isalpha():
            initials += word[0]
        
        # Extract numbers from word
        word_numbers = re.findall(r'\d+', word)
        if word_numbers:
            numbers += word_numbers[0]
    
    # Combine initials and numbers
    code = initials + numbers
    
    # Ensure minimum length
    if len(code) < 2:
        code = code.ljust(4, 'P')
    
    # Limit to reasonable length
    return code[:10]


def _extract_attribute_code(attribute: str) -> str:
    """
    Extract short code from attribute value.
    
    Examples:
        "Black" -> "BLK"
        "White" -> "WHT"
        "128GB" -> "128"
        "Large" -> "L"
        "Extra Large" -> "XL"
    """
    # Common size mappings
    size_map = {
        "extra small": "XS",
        "small": "S",
        "medium": "M",
        "large": "L",
        "extra large": "XL",
        "2xl": "XXL",
        "xxl": "XXL",
    }
    
    # Check if it's a known size
    lower_attr = attribute.lower().strip()
    if lower_attr in size_map:
        return size_map[lower_attr]
    
    # Extract numbers if present (for storage sizes like "128GB")
    numbers = re.findall(r'\d+', attribute)
    if numbers:
        return numbers[0]
    
    # Remove special characters
    cleaned = re.sub(r'[^a-zA-Z]', '', attribute)
    
    # If short word, take first 3 letters
    if len(cleaned) <= 5:
        return cleaned[:3]
    
    # For longer words, try to take initials of multiple words
    words = attribute.split()
    if len(words) > 1:
        return "".join(w[0] for w in words if w)
    
    # Otherwise take first 3 letters
    return cleaned[:3]


def validate_sku(sku: str) -> bool:
    """
    Validate SKU format.
    
    Rules:
    - Only alphanumeric and hyphens
    - Not empty
    - Reasonable length (3-50 chars)
    """
    if not sku or len(sku) < 3 or len(sku) > 50:
        return False
    
    # Check valid characters
    if not re.match(r'^[A-Z0-9-]+$', sku):
        return False
    
    return True
