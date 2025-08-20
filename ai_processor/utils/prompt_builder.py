"""Prompt building utilities for AI processing."""
import json
from pathlib import Path
from typing import List, Dict, Any
from .file_operations import get_variation_data, get_brand_info
from .ocr_utils import extract_all_ocr_text, is_ocr_available
from .ai_client import prepare_image_parts


def build_system_prompt() -> str:
    """Build the system prompt for nutrition analysis."""
    return """
You are an expert nutritionist and food scientist. Your task is to analyze images of a food product and its accompanying data to extract detailed nutritional and ingredient information.
You MUST provide the output in a structured JSON format that strictly adheres to the provided schema. Do not include any text, reasoning, or formatting outside of the JSON structure.

Key instructions:
1.  **Extract Core Details**: From the packaging, identify the `product_name`, `brand`, and `country_of_origin`. If a barcode (like a UPC or EAN) is visible, extract its number into the `barcode` field.

2.  **Net Quantity**: Extract `net_quantity_value` and `net_quantity_unit` from the packaging (e.g., "200g" → value: 200, unit: "g").

3.  **Standardize Nutrition Table**: The `nutrition_info_table` requires careful formatting:
    *   `nutrient`: Use standardized, common nutrient names. They must be **lowercase and snake_cased** (e.g., 'energy', 'total_fat', 'protein', 'dietary_fiber').
    *   `value`: Extract only the numerical value of the nutrient as a float.
    *   `unit`: Extract the unit of measurement (e.g., 'kcal', 'g', 'mg').
    *   `rda_percentage`: If RDA/% per serve is mentioned, extract it.

4.  **Serving Information**: 
    *   For `nutrition_serving_value` and `nutrition_serving_unit`, extract the serving size from text like "Per 150ml serving" or "Serving size: 100g".
    *   Extract `approx_serves_per_pack` if mentioned (e.g., "Approx. No. of serves per pack - 6").

5.  **Ingredient Analysis**: 
    *   `ingredients_string`: Extract the complete ingredients list exactly as written.
    *   `parsed_ingredients`: Parse each ingredient with:
        - `name`: Ingredient name
        - `percentage`: If percentage is mentioned (e.g., "Choco Crème (38.0%)")
        - `ins_numbers`: Extract INS numbers like ["503(ii)", "500(ii)", "450(i)"]
        - `additives`: Extract additive types like ["Emulsifier", "Stabilizer", "Raising Agent"]
        - `is_alarming`: Mark as true if ingredient is concerning for health
        - `alarming_reason`: Explain why if alarming
    *   `ins_numbers_found`: List all INS numbers found across all ingredients
    *   `preservatives`: Extract preservatives with their INS numbers and functions

6.  **Health & Safety Assessment**:
    *   `veg_non_veg`: Classify as one of these EXACT values: 'VEG', 'NON_VEG', 'VEGAN', or 'UNKNOWN'
    *   `alarming_ingredients`: List any concerning ingredients
    *   `health_rating`: Rate out of 100 considering all factors
    *   `processing_level`: Classify using NOVA food processing groups with EXACT values:
        - 'UNPROCESSED_MINIMAL_PROCESSED': Unprocessed foods (fresh fruits, vegetables, grains, legumes, fresh meat, eggs, milk) or minimally processed (dried, crushed, frozen, pasteurized) with no added salt, sugar, oils, fats, or additives
        - 'PROCESSED_CULINARY_INGREDIENTS': Substances derived from group 1 foods or nature (oils, salt, sugar, vinegar, starches, honey, butter) used for seasoning and cooking
        - 'PROCESSED_FOOD': Simple products made by adding culinary ingredients to unprocessed foods (cheese, canned vegetables, salted nuts, fruits in syrup, breads made with basic ingredients)
        - 'ULTRA_PROCESSED': Industrial formulations with multiple ingredients including substances of no culinary use (high-fructose corn syrup, hydrogenated oils, modified starches, protein isolates, artificial flavors, colors, emulsifiers)
    *   Generate balanced `positive_health_aspects` and `negative_health_aspects`

7.  **Additional Information**: Extract `storage_instructions`, `cooking_instructions`, `allergens`, and `certifications`.

IMPORTANT: Pay special attention to INS numbers (e.g., INS 503(ii), INS 500(ii), INS 450(i)) and additive classifications (Emulsifier, Stabilizer, etc.). These are crucial for downstream API lookups.
"""


def build_prompt_parts(variation_path: Path, enable_ocr: bool = True) -> List:
    """Build complete prompt parts for Gemini API."""
    # Get variation data
    variation_data = get_variation_data(variation_path)
    brand_info = get_brand_info(variation_path.parent)
    
    # Get image paths
    images_dir = variation_path / "images"
    image_paths = list(images_dir.glob("*")) if images_dir.exists() else []
    
    # Build prompt parts
    prompt_parts = [
        build_system_prompt(),
        "\n=== Product Data ===",
        json.dumps(variation_data, indent=2),
        "\n=== Brand Information ===",
        json.dumps(brand_info, indent=2),
    ]
    
    # Add OCR text if available and enabled
    if enable_ocr and is_ocr_available() and image_paths:
        ocr_text = extract_all_ocr_text(image_paths)
        if ocr_text:
            prompt_parts.extend([
                "\n=== OCR Extracted Text ===",
                ocr_text
            ])
    
    # Add instruction
    prompt_parts.append(
        "\nPlease analyze the attached images, product data, and OCR text to extract comprehensive nutrition and ingredient information."
    )
    
    # Add image parts
    image_parts = prepare_image_parts(image_paths)
    prompt_parts.extend(image_parts)
    
    return prompt_parts, image_paths
