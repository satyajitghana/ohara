"""Script to migrate scraped data to the database."""
import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Set
from sqlmodel import Session, create_engine, select
from sqlalchemy.exc import IntegrityError

from ..models import (
    Brand, Product, NutritionFact, Ingredient,
    VegStatus, ProcessingLevel
)
from ..database import engine, create_db_and_tables

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_json_file(file_path: Path) -> Dict[str, Any]:
    """Load JSON file safely."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError) as e:
        logger.error(f"Error loading {file_path}: {e}")
        return {}


def safe_float(value: Any) -> float | None:
    """Safely convert value to float."""
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (ValueError, TypeError):
        return None


def safe_int(value: Any) -> int | None:
    """Safely convert value to int."""
    if value is None or value == "":
        return None
    try:
        return int(value)
    except (ValueError, TypeError):
        return None


def safe_enum(value: Any, enum_class) -> Any:
    """Safely convert value to enum."""
    if value is None or value == "":
        return None
    try:
        if hasattr(enum_class, value):
            return getattr(enum_class, value)
        return None
    except (ValueError, TypeError):
        return None


def migrate_brand(session: Session, brand_data: Dict[str, Any]) -> Brand:
    """Migrate a single brand."""
    brand_id = brand_data.get("brand_id")
    brand_name = brand_data.get("brand_name")
    
    if not brand_id or not brand_name:
        raise ValueError(f"Invalid brand data: {brand_data}")
    
    # Check if brand already exists
    statement = select(Brand).where(Brand.original_brand_id == brand_id)
    existing_brand = session.exec(statement).first()
    
    if existing_brand:
        return existing_brand
    
    # Create new brand
    brand = Brand(
        name=brand_name,
        original_brand_id=brand_id
    )
    session.add(brand)
    session.commit()
    session.refresh(brand)
    
    logger.info(f"Created brand: {brand_name}")
    return brand


def migrate_product(session: Session, product_data: Dict[str, Any], variation_data: Dict[str, Any], 
                   ai_data: Dict[str, Any], brand: Brand, image_paths: List[str], 
                   catalog_images: List[str], seen_barcodes: Set[str]) -> Product | None:
    """Migrate a single product with its variation and AI data."""
    
    variation = variation_data.get("variation", {})
    price_info = variation.get("price", {})
    
    # Check for barcode conflicts
    barcode = ai_data.get("barcode")
    existing_product = None
    
    if barcode and barcode.strip():
        barcode = barcode.strip()
        
        # Check if we've already seen this barcode in this migration session
        if barcode in seen_barcodes:
            logger.warning(f"Duplicate barcode {barcode} found for product {variation.get('display_name', '')} - skipping")
            return None
        
        # Check if barcode already exists in database
        existing_product = session.exec(select(Product).where(Product.barcode == barcode)).first()
        if existing_product:
            logger.info(f"Barcode {barcode} already exists for product {existing_product.display_name} - updating with new data from {variation.get('display_name', '')}")
        
        seen_barcodes.add(barcode)
    else:
        barcode = None
    
    # Map VEG status
    veg_status_str = ai_data.get("veg_non_veg")
    veg_status = safe_enum(veg_status_str, VegStatus)
    
    # Map processing level
    processing_level_str = ai_data.get("processing_level")
    processing_level = safe_enum(processing_level_str, ProcessingLevel)
    
    # Update existing product or create new one
    if existing_product:
        # Update existing product with new data
        existing_product.name = ai_data.get("product_name") or variation.get("product_name_without_brand", "") or existing_product.name
        existing_product.display_name = variation.get("display_name", "") or existing_product.display_name
        existing_product.brand_id = brand.id
        
        # Update pricing if available
        if price_info.get("mrp"): existing_product.mrp = safe_float(price_info.get("mrp"))
        if price_info.get("store_price"): existing_product.store_price = safe_float(price_info.get("store_price"))
        if price_info.get("offer_price"): existing_product.offer_price = safe_float(price_info.get("offer_price"))
        if price_info.get("discount_value"): existing_product.discount_value = safe_float(price_info.get("discount_value"))
        
        # Update product details
        if variation.get("quantity"): existing_product.quantity = variation.get("quantity")
        if variation.get("unit_of_measure"): existing_product.unit_of_measure = variation.get("unit_of_measure")
        if variation.get("weight_in_grams"): existing_product.weight_in_grams = safe_float(variation.get("weight_in_grams"))
        
        # Update categories
        if variation.get("category"): existing_product.category = variation.get("category")
        if variation.get("super_category"): existing_product.super_category = variation.get("super_category")
        if variation.get("sub_category_l3"): existing_product.sub_category_l3 = variation.get("sub_category_l3")
        if variation.get("sub_category_l4"): existing_product.sub_category_l4 = variation.get("sub_category_l4")
        if variation.get("sub_category_l5"): existing_product.sub_category_l5 = variation.get("sub_category_l5")
        
        # Update AI data
        if ai_data.get("net_quantity_value"): existing_product.net_quantity_value = safe_float(ai_data.get("net_quantity_value"))
        if ai_data.get("net_quantity_unit"): existing_product.net_quantity_unit = ai_data.get("net_quantity_unit")
        if veg_status: existing_product.veg_status = veg_status
        if ai_data.get("health_rating"): existing_product.health_rating = safe_int(ai_data.get("health_rating"))
        if processing_level: existing_product.processing_level = processing_level
        if ai_data.get("country_of_origin"): existing_product.country_of_origin = ai_data.get("country_of_origin")
        
        # Update text fields
        if ai_data.get("ingredients_string"): existing_product.ingredients_string = ai_data.get("ingredients_string")
        if ai_data.get("allergens"): existing_product.allergens = json.dumps(ai_data.get("allergens", []))
        if ai_data.get("certifications"): existing_product.certifications = json.dumps(ai_data.get("certifications", []))
        if ai_data.get("positive_health_aspects"): existing_product.positive_health_aspects = json.dumps(ai_data.get("positive_health_aspects", []))
        if ai_data.get("negative_health_aspects"): existing_product.negative_health_aspects = json.dumps(ai_data.get("negative_health_aspects", []))
        if ai_data.get("storage_instructions"): existing_product.storage_instructions = ai_data.get("storage_instructions")
        if ai_data.get("cooking_instructions"): existing_product.cooking_instructions = ai_data.get("cooking_instructions")
        
        # Update nutrition info
        if ai_data.get("nutrition_serving_value"): existing_product.nutrition_serving_value = safe_float(ai_data.get("nutrition_serving_value"))
        if ai_data.get("nutrition_serving_unit"): existing_product.nutrition_serving_unit = ai_data.get("nutrition_serving_unit")
        if ai_data.get("approx_serves_per_pack"): existing_product.approx_serves_per_pack = safe_int(ai_data.get("approx_serves_per_pack"))
        
        # Update images
        if image_paths: existing_product.image_paths = json.dumps(image_paths)
        if catalog_images: existing_product.catalog_images = json.dumps(catalog_images)
        
        existing_product.updated_at = datetime.utcnow()
        
        try:
            session.commit()
            session.refresh(existing_product)
            existing_product._is_updated = True  # Mark as updated for nutrition/ingredients migration
            logger.info(f"Updated existing product: {existing_product.display_name}")
            return existing_product
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Database integrity error updating product {existing_product.display_name}: {e}")
            return None
    else:
        # Create new product
        product = Product(
            name=ai_data.get("product_name") or variation.get("product_name_without_brand", ""),
            display_name=variation.get("display_name", ""),
            original_product_id=product_data.get("product_id", ""),
            brand_id=brand.id,
            
            # Pricing
            mrp=safe_float(price_info.get("mrp")),
            store_price=safe_float(price_info.get("store_price")),
            offer_price=safe_float(price_info.get("offer_price")),
            discount_value=safe_float(price_info.get("discount_value")),
            
            # Product details
            quantity=variation.get("quantity"),
            unit_of_measure=variation.get("unit_of_measure"),
            weight_in_grams=safe_float(variation.get("weight_in_grams")),
            
            # Categories
            category=variation.get("category"),
            super_category=variation.get("super_category"),
            sub_category_l3=variation.get("sub_category_l3"),
            sub_category_l4=variation.get("sub_category_l4"),
            sub_category_l5=variation.get("sub_category_l5"),
            
            # AI data
            barcode=barcode,
            net_quantity_value=safe_float(ai_data.get("net_quantity_value")),
            net_quantity_unit=ai_data.get("net_quantity_unit"),
            veg_status=veg_status,
            health_rating=safe_int(ai_data.get("health_rating")),
            processing_level=processing_level,
            country_of_origin=ai_data.get("country_of_origin"),
            
            # Text fields
            ingredients_string=ai_data.get("ingredients_string"),
            allergens=json.dumps(ai_data.get("allergens", [])) if ai_data.get("allergens") else None,
            certifications=json.dumps(ai_data.get("certifications", [])) if ai_data.get("certifications") else None,
            positive_health_aspects=json.dumps(ai_data.get("positive_health_aspects", [])) if ai_data.get("positive_health_aspects") else None,
            negative_health_aspects=json.dumps(ai_data.get("negative_health_aspects", [])) if ai_data.get("negative_health_aspects") else None,
            storage_instructions=ai_data.get("storage_instructions"),
            cooking_instructions=ai_data.get("cooking_instructions"),
            
            # Nutrition info
            nutrition_serving_value=safe_float(ai_data.get("nutrition_serving_value")),
            nutrition_serving_unit=ai_data.get("nutrition_serving_unit"),
            approx_serves_per_pack=safe_int(ai_data.get("approx_serves_per_pack")),
            
            # Images
            image_paths=json.dumps(image_paths) if image_paths else None,
            catalog_images=json.dumps(catalog_images) if catalog_images else None
        )
        
        try:
            session.add(product)
            session.commit()
            session.refresh(product)
            
            logger.info(f"Created product: {product.display_name}")
            return product
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Database integrity error for product {product.display_name}: {e}")
            return None


def migrate_nutrition_facts(session: Session, product: Product, ai_data: Dict[str, Any], is_update: bool = False):
    """Migrate nutrition facts for a product."""
    nutrition_table = ai_data.get("nutrition_info_table", [])
    
    if is_update:
        # Clear existing nutrition facts
        existing_nutrition = session.exec(select(NutritionFact).where(NutritionFact.product_id == product.id)).all()
        for nutrition in existing_nutrition:
            session.delete(nutrition)
    
    for nutrition_item in nutrition_table:
        if not isinstance(nutrition_item, dict):
            continue
            
        nutrition_fact = NutritionFact(
            product_id=product.id,
            nutrient=nutrition_item.get("nutrient", ""),
            value=safe_float(nutrition_item.get("value")) or 0.0,
            unit=nutrition_item.get("unit", ""),
            rda_percentage=safe_float(nutrition_item.get("rda_percentage"))
        )
        session.add(nutrition_fact)
    
    if nutrition_table:
        session.commit()
        action = "Updated" if is_update else "Added"
        logger.info(f"{action} {len(nutrition_table)} nutrition facts for {product.display_name}")


def migrate_ingredients(session: Session, product: Product, ai_data: Dict[str, Any], is_update: bool = False):
    """Migrate ingredients for a product."""
    parsed_ingredients = ai_data.get("parsed_ingredients", [])
    
    if is_update:
        # Clear existing ingredients
        existing_ingredients = session.exec(select(Ingredient).where(Ingredient.product_id == product.id)).all()
        for ingredient in existing_ingredients:
            session.delete(ingredient)
    
    for ingredient_data in parsed_ingredients:
        if not isinstance(ingredient_data, dict):
            continue
            
        ingredient = Ingredient(
            product_id=product.id,
            name=ingredient_data.get("name", ""),
            percentage=safe_float(ingredient_data.get("percentage")),
            ins_numbers=json.dumps(ingredient_data.get("ins_numbers", [])) if ingredient_data.get("ins_numbers") else None,
            additives=json.dumps(ingredient_data.get("additives", [])) if ingredient_data.get("additives") else None,
            is_alarming=ingredient_data.get("is_alarming", False),
            alarming_reason=ingredient_data.get("alarming_reason")
        )
        session.add(ingredient)
    
    if parsed_ingredients:
        session.commit()
        action = "Updated" if is_update else "Added"
        logger.info(f"{action} {len(parsed_ingredients)} ingredients for {product.display_name}")


def get_image_data(variation_dir: Path, variation_data: Dict[str, Any]) -> tuple[List[str], List[str]]:
    """Get image paths and catalog image names for a variation."""
    images_dir = variation_dir / "images"
    
    # Get the list of image filenames from variation data
    variation = variation_data.get("variation", {})
    catalog_images = variation.get("images", [])
    
    if not images_dir.exists():
        return [], catalog_images
    
    # Create a mapping from filename to full path
    available_files = {}
    for image_file in images_dir.iterdir():
        if image_file.is_file():
            available_files[image_file.name] = str(image_file.relative_to(Path("scraped_data")))
    
    # Match catalog images with available files
    image_paths = []
    for catalog_image in catalog_images:
        # Extract filename from catalog path (e.g., "NI_CATALOG/.../filename.png" -> "filename.png")
        filename = Path(catalog_image).name
        
        if filename in available_files:
            image_paths.append(available_files[filename])
        else:
            logger.warning(f"Image file {filename} not found in {images_dir}")
    
    # Add any additional files that weren't in the catalog (just in case)
    for filename, path in available_files.items():
        if path not in image_paths:
            image_paths.append(path)
    
    return image_paths, catalog_images


def migrate_scraped_data():
    """Main migration function."""
    logger.info("Starting data migration...")
    
    # Create tables
    create_db_and_tables()
    
    scraped_data_dir = Path("scraped_data")
    if not scraped_data_dir.exists():
        logger.error("scraped_data directory not found!")
        return
    
    migrated_brands = 0
    migrated_products = 0
    skipped_products = 0
    errors = 0
    seen_barcodes: Set[str] = set()
    
    with Session(engine) as session:
        # Iterate through brand directories
        for brand_dir in scraped_data_dir.iterdir():
            if not brand_dir.is_dir():
                continue
                
            try:
                # Load brand info
                brand_info_file = brand_dir / "brand_info.json"
                if not brand_info_file.exists():
                    logger.warning(f"No brand_info.json found in {brand_dir}")
                    continue
                
                brand_data = load_json_file(brand_info_file)
                if not brand_data:
                    continue
                
                # Migrate brand
                brand = migrate_brand(session, brand_data)
                migrated_brands += 1
                
                # Load products list
                products_list_file = brand_dir / "products_list.json"
                if not products_list_file.exists():
                    logger.warning(f"No products_list.json found in {brand_dir}")
                    continue
                
                products_list = load_json_file(products_list_file)
                products_info = products_list.get("products_info", {})
                
                # Iterate through product variations
                for variation_dir in brand_dir.iterdir():
                    if not variation_dir.is_dir() or variation_dir.name in ["images"]:
                        continue
                    
                    try:
                        # Load variation data
                        data_file = variation_dir / "data.json"
                        ai_file = variation_dir / "parsed_ai.json"
                        
                        if not data_file.exists():
                            logger.warning(f"No data.json found in {variation_dir}")
                            continue
                        
                        variation_data = load_json_file(data_file)
                        ai_data = load_json_file(ai_file) if ai_file.exists() else {}
                        
                        # Get parent product info
                        parent_product = variation_data.get("parent_product", {})
                        product_id = parent_product.get("product_id")
                        
                        if not product_id or product_id not in products_info:
                            logger.warning(f"Product ID {product_id} not found in products_info")
                            continue
                        
                        product_info = products_info[product_id]
                        
                        # Get image data
                        image_paths, catalog_images = get_image_data(variation_dir, variation_data)
                        
                        # Check if product already exists
                        statement = select(Product).where(Product.original_product_id == product_id)
                        existing_product = session.exec(statement).first()
                        
                        if existing_product:
                            logger.info(f"Product {product_id} already exists, skipping...")
                            continue
                        
                        # Migrate product
                        product = migrate_product(
                            session, product_info, variation_data, ai_data, brand, image_paths, catalog_images, seen_barcodes
                        )
                        
                        if product:
                            migrated_products += 1
                            
                            # Migrate nutrition facts and ingredients
                            if ai_data:
                                is_update = hasattr(product, '_is_updated') and product._is_updated
                                migrate_nutrition_facts(session, product, ai_data, is_update)
                                migrate_ingredients(session, product, ai_data, is_update)
                        else:
                            skipped_products += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing variation {variation_dir}: {e}")
                        errors += 1
                        continue
                
            except Exception as e:
                logger.error(f"Error processing brand {brand_dir}: {e}")
                errors += 1
                continue
    
    logger.info("\nMigration completed!")
    logger.info(f"Brands migrated: {migrated_brands}")
    logger.info(f"Products migrated: {migrated_products}")
    logger.info(f"Products skipped (duplicate barcode): {skipped_products}")
    logger.info(f"Errors: {errors}")
    
    if skipped_products > 0:
        logger.warning(f"⚠️  {skipped_products} products were skipped due to duplicate barcodes. Check logs above for details.")


if __name__ == "__main__":
    migrate_scraped_data()
