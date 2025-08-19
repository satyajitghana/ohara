from google import genai
from google.genai import types
from pydantic import BaseModel, Field
from typing import List, Optional
import json
from pathlib import Path
import os
import multiprocessing
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
import logging

# --- Pydantic Schemas (same as process_images.py) ---

class NutritionInfo(BaseModel):
    """Represents a single nutrient entry in the nutrition table."""
    nutrient: str = Field(description="Name of the nutrient (e.g., 'energy', 'protein', 'total_fat'), always lowercase, snake_cased, and standardized.")
    value: float = Field(description="Numerical value of the nutrient.")
    unit: str = Field(description="Unit for the nutrient value (e.g., 'kcal', 'g', 'mg').")

class AiResponse(BaseModel):
    """The structured response from the AI model."""
    product_name: Optional[str] = Field(default=None, description="The name of the product.")
    brand: Optional[str] = Field(default=None, description="The brand of the product.")
    barcode: Optional[str] = Field(default=None, description="The product's barcode (EAN/UPC), if visible on any of the images.")
    nutrition_info_table: List[NutritionInfo] = Field(description="A standard table of nutritional information.")
    nutrition_serving_value: float = Field(description="The serving size value the nutrition information is based on (e.g., 100, 150).")
    nutrition_serving_unit: str = Field(description="The serving size unit (e.g., 'g', 'ml', 'serving').")
    ingredients: List[str] = Field(description="List of ingredients.")
    additives: List[str] = Field(description="List of additives, if any.")
    allergens: List[str] = Field(description="List of allergens, if any.")
    health_rating: int = Field(description="A health rating out of 100, decided by the AI.", ge=0, le=100)
    processing_level: str = Field(description="The level of food processing (e.g., 'Unprocessed', 'Minally Processed', 'Processed', 'Ultra-processed').")
    positive_health_aspects: List[str] = Field(description="A list of generated positive health aspects based on ingredients and nutritional values (e.g., 'Good source of protein', 'Low in sodium').")
    negative_health_aspects: List[str] = Field(description="A list of generated negative health aspects based on ingredients and nutritional values (e.g., 'High in added sugar', 'Contains artificial sweeteners').")
    storage_instructions: Optional[str] = Field(default=None, description="Instructions for storing the product.")
    cooking_instructions: Optional[str] = Field(default=None, description="Instructions for cooking or preparing the product.")
    country_of_origin: Optional[str] = Field(default=None, description="The country where the product was made.")
    certifications: List[str] = Field(description="List of certifications found on the packaging (e.g., 'Organic', 'Non-GMO', 'Gluten-Free').")

# --- Configuration and Logging Setup ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_api_key(config_path: Path = Path("config.json")):
    """Loads the Gemini API key from the config file."""
    try:
        with open(config_path, 'r') as f:
            config = json.load(f)
        api_key = config.get("gemini_api_key")
        if not api_key:
            raise ValueError("API key not found in config.json")
        return api_key
    except FileNotFoundError:
        logging.error("config.json not found. Please create it with your API key.")
        raise
    except json.JSONDecodeError:
        logging.error("Could not decode config.json. Please ensure it's valid JSON.")
        raise

# --- Core Processing Functions ---

def get_mime_type(image_path: Path) -> str:
    """Returns the MIME type based on the image file extension."""
    suffix = image_path.suffix.lower()
    if suffix in [".jpg", ".jpeg"]:
        return "image/jpeg"
    elif suffix == ".png":
        return "image/png"
    elif suffix == ".webp":
        return "image/webp"
    else:
        return "application/octet-stream"

def prepare_model_input(variation_path: Path) -> (list, List[Path]):
    """Prepares the model prompt with inline image data."""
    product_data = {}
    product_data_path = variation_path.parent / "data.json"
    if product_data_path.exists():
        with open(product_data_path, 'r', encoding='utf-8') as f:
            product_data = json.load(f)

    system_prompt = """
You are an expert nutritionist and food scientist. Your task is to analyze images of a food product and its accompanying data to extract detailed nutritional and ingredient information.
You MUST provide the output in a structured JSON format that strictly adheres to the provided schema. Do not include any text, reasoning, or formatting outside of the JSON structure.
Key instructions:
1.  **Extract Core Details**: From the packaging, identify the `product_name`, `brand`, and `country_of_origin`. If a barcode (like a UPC or EAN) is visible, extract its number into the `barcode` field.
2.  **Standardize Nutrition Table**: The `nutrition_info_table` requires careful formatting:
    *   `nutrient`: Use standardized, common nutrient names. They must be **lowercase and snake_cased** (e.g., 'energy', 'total_fat', 'protein', 'dietary_fiber').
    *   `value`: Extract only the numerical value of the nutrient as a float.
    *   `unit`: Extract the unit of measurement (e.g., 'kcal', 'g', 'mg').
3.  **Serving Size**: For `nutrition_serving_value` and `nutrition_serving_unit`, extract the serving size from text like "Per 150ml serving" or "Serving size: 100g".
4.  **Analyze and Assess**: Based on the complete list of ingredients and nutritional data:
    *   Provide an objective `health_rating` out of 100.
    *   Determine the `processing_level`.
    *   Generate balanced lists for `positive_health_aspects` and `negative_health_aspects`. These should be concise, clear, and based on the product's data (e.g., positive: 'Good source of protein', negative: 'High in added sugar').
5.  **Find Actionable Information**: Extract any `storage_instructions`, `cooking_instructions`, and a list of `certifications` (like 'Organic', 'Non-GMO') visible on the packaging.
"""
    prompt_parts = [system_prompt, "Product Data:", json.dumps(product_data, indent=2), "\nPlease analyze the attached images and product data to extract the nutrition information."]
    
    images_dir = variation_path / "images"
    image_paths = list(images_dir.glob("*"))
    for image_path in image_paths:
        try:
            with open(image_path, 'rb') as f:
                image_bytes = f.read()
            mime_type = get_mime_type(image_path)
            prompt_parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime_type))
        except IOError as e:
            logging.warning(f"Could not read image {image_path}, skipping. Error: {e}")
            
    return prompt_parts, image_paths

def process_images_with_gemini(client, prompt_parts: list):
    """Sends data to Gemini and gets the structured nutritional information."""
    response = client.models.generate_content(
        model='gemini-2.5-flash',
        contents=prompt_parts,
        config={
            "response_mime_type": "application/json",
            "response_schema": AiResponse,
        }
    )
    return response

def save_output(variation_path: Path, ai_data: dict):
    """Saves the AI's response to parsed_ai.json."""
    output_path = variation_path / "parsed_ai.json"
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(ai_data, f, indent=2, ensure_ascii=False)

def process_variation(variation_path: Path):
    """Worker function to process a single product variation."""
    try:
        if (variation_path / "parsed_ai.json").exists():
            # logging.info(f"Skipping already processed variation: {variation_path}")
            return f"Skipped: {variation_path.parent.name}/{variation_path.name}"

        # The API key is set as an environment variable in the main process
        client = genai.Client()

        prompt_parts, image_paths = prepare_model_input(variation_path)

        if not image_paths:
            return f"No images: {variation_path.parent.name}/{variation_path.name}"

        response = process_images_with_gemini(client, prompt_parts)
        
        if response.parsed:
            ai_output_dict = response.parsed.model_dump()
            save_output(variation_path, ai_output_dict)
            return f"Success: {variation_path.parent.name}/{variation_path.name}"
        else:
            # Fallback to parsing text if .parsed is not available
            try:
                cleaned_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
                ai_output_dict = json.loads(cleaned_text)
                save_output(variation_path, ai_output_dict)
                return f"Success (fallback): {variation_path.parent.name}/{variation_path.name}"
            except json.JSONDecodeError:
                 return f"JSON Error: {variation_path.parent.name}/{variation_path.name}"

    except Exception as e:
        logging.error(f"Failed to process {variation_path}: {e}")
        return f"Error: {variation_path.parent.name}/{variation_path.name} - {e}"

# --- Main Execution ---

def main():
    """Main function to find and process all products in parallel."""
    try:
        api_key = load_api_key()
        os.environ["GEMINI_API_KEY"] = api_key # Set for worker processes
    except (FileNotFoundError, ValueError) as e:
        return

    base_path = Path("scraped_data")
    all_variation_paths = [
        v for p in base_path.iterdir() if p.is_dir()
        for v in p.iterdir() if v.is_dir() and (v / "images").exists() and any((v / "images").iterdir())
    ]
    
    if not all_variation_paths:
        logging.info("No product variations with images found to process.")
        return

    logging.info(f"Found {len(all_variation_paths)} product variations to process.")

    # Number of parallel processes
    num_processes = 100

    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed} of {task.total})"),
        TimeRemainingColumn(),
    ) as progress:
        task = progress.add_task("[cyan]Processing Products...", total=len(all_variation_paths))

        with multiprocessing.Pool(processes=num_processes) as pool:
            for i, result in enumerate(pool.imap_unordered(process_variation, all_variation_paths)):
                progress.update(task, advance=1, description=f"[cyan]Processing... {result}")

    logging.info("✅ All product variations processed.")

if __name__ == "__main__":
    main()
