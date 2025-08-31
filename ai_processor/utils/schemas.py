"""Pydantic schemas for AI processor structured output."""
from pydantic import BaseModel, Field
from typing import List, Optional
from enum import Enum


class VegNonVegClassification(str, Enum):
    """Vegetarian classification options."""
    VEG = "VEG"
    NON_VEG = "NON_VEG"
    VEGAN = "VEGAN"
    UNKNOWN = "UNKNOWN"


class ProcessingLevel(str, Enum):
    """NOVA food processing classification levels."""
    UNPROCESSED_MINIMAL_PROCESSED = "UNPROCESSED_MINIMAL_PROCESSED"
    PROCESSED_CULINARY_INGREDIENTS = "PROCESSED_CULINARY_INGREDIENTS"
    PROCESSED_FOOD = "PROCESSED_FOOD"
    ULTRA_PROCESSED = "ULTRA_PROCESSED"


class NutritionInfo(BaseModel):
    """Represents a single nutrient entry in the nutrition table."""
    nutrient: str = Field(description="Standardized nutrient name: 'energy', 'total_carbohydrates', 'total_sugars', 'added_sugars', 'total_fat', 'saturated_fat', 'trans_fat', 'protein', 'dietary_fiber', 'sodium', 'cholesterol' - always lowercase and snake_cased.")
    value: float = Field(description="Numerical value of the nutrient.")
    unit: str = Field(description="Unit for the nutrient value (e.g., 'kcal', 'kj', 'g', 'mg', 'mcg').")
    rda_percentage: Optional[float] = Field(default=None, description="RDA percentage per serve if available on the label.")


class ParsedIngredient(BaseModel):
    """Represents a parsed ingredient with detailed information."""
    name: str = Field(description="The ingredient name (e.g., 'Sugar', 'Refined Palm Oil', 'Cocoa Solids').")
    percentage: Optional[float] = Field(default=None, description="Percentage of this ingredient if mentioned (e.g., 38.0 for 'Choco Crème (38.0%)').")
    ins_numbers: List[str] = Field(default=[], description="List of INS numbers associated with this ingredient (e.g., ['503(ii)', '500(ii)', 'E322']).")
    additives: List[str] = Field(default=[], description="List of additive types for this ingredient (e.g., ['Emulsifier', 'Preservative', 'Artificial Color']).")
    is_alarming: bool = Field(default=False, description="Whether this ingredient is concerning for health (palm oil, trans fats, artificial additives, excessive preservatives, etc.).")
    alarming_reason: Optional[str] = Field(default=None, description="Detailed explanation of health concerns if is_alarming is True (e.g., 'Palm oil linked to deforestation and potential health risks', 'Artificial color may cause hyperactivity in children').")


class Preservative(BaseModel):
    """Represents a preservative with its INS number and details."""
    name: str = Field(description="Name of the preservative (e.g., 'Sodium Benzoate', 'Potassium Sorbate').")
    ins_number: Optional[str] = Field(default=None, description="INS number of the preservative (e.g., '211', '202').")
    function: Optional[str] = Field(default=None, description="Function of the preservative (e.g., 'Preservative', 'Antioxidant').")


class AiResponse(BaseModel):
    """The structured response from the AI model."""
    product_name: Optional[str] = Field(default=None, description="The name of the product.")
    brand: Optional[str] = Field(default=None, description="The brand of the product.")
    barcode: Optional[str] = Field(default=None, description="The product's barcode (EAN/UPC), if visible on any of the images. This is CRITICAL to extract.")
    
    # Net quantity information
    net_quantity_value: Optional[float] = Field(default=None, description="The net quantity value (e.g., 200, 1.5).")
    net_quantity_unit: Optional[str] = Field(default=None, description="The net quantity unit (e.g., 'g', 'ml', 'kg', 'l').")
    
    # Nutrition information
    nutrition_info_table: List[NutritionInfo] = Field(description="A standard table of nutritional information.")
    nutrition_info_quantity: float = Field(description="The quantity per which nutrition information is provided (e.g., 100, 40, 150). This is NOT serving size, but the base quantity for nutrition facts.")
    nutrition_info_unit: str = Field(description="The unit for nutrition info quantity (e.g., 'g', 'ml').")
    approx_serves_per_pack: Optional[int] = Field(default=None, description="Approximate number of serves per pack if mentioned on the packaging.")
    
    # Ingredient information
    ingredients_string: str = Field(description="The raw ingredients list as a string, exactly as it appears on the packaging.")
    parsed_ingredients: List[ParsedIngredient] = Field(description="Parsed and structured ingredients with detailed information.")
    
    # Preservatives and additives
    preservatives: List[Preservative] = Field(default=[], description="List of preservatives found in the product.")
    ins_numbers_found: List[str] = Field(default=[], description="All INS numbers found in the ingredient list (e.g., ['503(ii)', '500(ii)', '450(i)']).")
    
    # Classification and tags
    veg_non_veg: Optional[VegNonVegClassification] = Field(default=None, description="Product classification based on vegetarian status.")
    tags: List[str] = Field(default=[], description="Relevant tags for product searchability (e.g., 'organic', 'high-protein', 'gluten-free', 'snack', 'beverage', 'instant', 'processed').")
    
    # Health and safety
    additives: List[str] = Field(description="List of additives, if any.")
    allergens: List[str] = Field(description="List of allergens, if any.")
    alarming_ingredients: List[str] = Field(default=[], description="List of ingredients that are considered alarming for health, especially carcinogens, palm oil, artificial additives.")
    carcinogens_detected: List[str] = Field(default=[], description="List of known or suspected carcinogens found in the product (nitrates, BHA, BHT, harmful artificial colors, etc.).")
    health_rating: int = Field(description="A health rating out of 100, decided by the AI.", ge=0, le=100)
    health_rating_explanation: str = Field(description="Detailed explanation starting with base category score (raw=95-100, minimally processed=85-95, etc.), then listing all specific additions and deductions with reasons.")
    processing_level: ProcessingLevel = Field(description="The NOVA food processing classification level.")
    positive_health_aspects: List[str] = Field(description="A list of generated positive health aspects based on ingredients and nutritional values (e.g., 'Good source of protein', 'Low in sodium', 'Contains natural ingredients').")
    negative_health_aspects: List[str] = Field(description="A list of generated negative health aspects based on ingredients and nutritional values (e.g., 'High in added sugar', 'Contains palm oil', 'High in artificial preservatives').")
    
    # Additional information
    storage_instructions: Optional[str] = Field(default=None, description="Instructions for storing the product.")
    cooking_instructions: Optional[str] = Field(default=None, description="Instructions for cooking or preparing the product.")
    country_of_origin: Optional[str] = Field(default=None, description="The country where the product was made.")
    certifications: List[str] = Field(description="List of certifications found on the packaging (e.g., 'Organic', 'Non-GMO', 'Gluten-Free').")
