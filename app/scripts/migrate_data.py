"""Script to migrate scraped data to the database."""
import json
import os
import logging
from pathlib import Path
from datetime import datetime
from typing import Dict, Any, List, Set, Optional
from sqlmodel import Session, create_engine, select
from sqlalchemy.exc import IntegrityError

from ..models import (
    Brand, SuperCategory, Category, Product, ProductImage,
    NutritionFact, Ingredient, DataSource, VegStatus, ProcessingLevel
)
from ..database import engine, create_db_and_tables

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def load_json_file(file_path: Path) -> Dict[str, Any] | List[Any]:
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


def migrate_super_categories(session: Session) -> Dict[str, SuperCategory]:
    """Migrate super categories from super_categories.json."""
    logger.info("Migrating super categories from super_categories.json...")
    super_categories_file = Path("scraped_data/swiggy/categories/super_categories.json")
    super_category_map = {}

    if not super_categories_file.exists():
        logger.error("super_categories.json not found!")
        return {}

    super_categories_data = load_json_file(super_categories_file)
    if not isinstance(super_categories_data, list):
        logger.error("Invalid super_categories.json format")
        return {}

    for sc_data in super_categories_data:
        name = sc_data.get("description")
        if not name:
            continue

        statement = select(SuperCategory).where(SuperCategory.name == name)
        existing_sc = session.exec(statement).first()

        if existing_sc:
            super_category_map[name] = existing_sc
            continue

        image_filename = sc_data.get("image_filename")
        image_path = f"swiggy/categories/images/{image_filename}" if image_filename else None

        super_category = SuperCategory(
            name=name,
            image_filename=image_path,
            taxonomy_type=sc_data.get("taxonomyType")
        )
        session.add(super_category)
        try:
            session.commit()
            session.refresh(super_category)
            super_category_map[name] = super_category
        except IntegrityError:
            session.rollback()
            existing_sc = session.exec(select(SuperCategory).where(SuperCategory.name == name)).one()
            super_category_map[name] = existing_sc

    logger.info(f"Loaded {len(super_category_map)} super categories.")
    return super_category_map


def migrate_categories_and_build_map(session: Session, super_category_map: Dict[str, SuperCategory]) -> Dict[str, Category]:
    """Migrate categories from metadata files and build a mapping."""
    logger.info("Migrating categories from metadata files...")
    categories_dir = Path("scraped_data/swiggy/categories")
    category_map: Dict[str, Category] = {}

    for metadata_file in categories_dir.glob("*_metadata.json"):
        super_category_name_from_file = metadata_file.stem.replace("_metadata", "").replace("_", " ")

        super_category = super_category_map.get(super_category_name_from_file)
        if not super_category:
            logger.warning(f"SuperCategory '{super_category_name_from_file}' from file name not in map. Skipping {metadata_file.name}")
            continue

        metadata = load_json_file(metadata_file)
        if not isinstance(metadata, dict):
            continue

        # Process items in "filters" as the actual categories
        items_to_process = metadata.get("filters", [])
        
        # Add the main category itself to the list of items to process
        main_category_name = metadata.get("selected_category", {}).get("name")
        if main_category_name:
            main_category_data = next((c for c in metadata.get("categories", []) if c.get("display_name") == main_category_name), None)
            if main_category_data:
                # To make it compatible with filter items, we rename 'display_name' to 'name'
                main_category_data['name'] = main_category_data.pop('display_name')
                items_to_process.append(main_category_data)

        for item in items_to_process:
            category_name = item.get("name")
            if not category_name:
                continue

            statement = select(Category).where(Category.name == category_name, Category.super_category_id == super_category.id)
            existing_cat = session.exec(statement).first()

            if existing_cat:
                if category_name not in category_map:
                    category_map[category_name] = existing_cat
                continue

            image_filename = item.get("image_filename")
            image_path = f"swiggy/categories/images/{image_filename}" if image_filename else None

            category = Category(
                name=category_name,
                image_filename=image_path,
                super_category_id=super_category.id,
                product_count=item.get("product_count", 0),
                age_consent_required=item.get("age_consent_required", False)
            )
            session.add(category)
            try:
                session.commit()
                session.refresh(category)
                if category_name not in category_map:
                    category_map[category_name] = category
                logger.info(f"Created Category: '{category_name}' under SuperCategory: '{super_category.name}'")
            except IntegrityError:
                session.rollback()
                existing_cat = session.exec(select(Category).where(Category.name == category_name, Category.super_category_id == super_category.id)).first()
                if existing_cat and category_name not in category_map:
                    category_map[category_name] = existing_cat

    logger.info(f"Built map with {len(category_map)} categories.")
    return category_map


def migrate_brand(session: Session, brand_data: Dict[str, Any]) -> Optional[Brand]:
    """Migrate a single brand."""
    brand_name = brand_data.get("brand_name")
    if not brand_name:
        return None
    
    statement = select(Brand).where(Brand.name == brand_name)
    existing_brand = session.exec(statement).first()
    
    if existing_brand:
        return existing_brand
    
    brand = Brand(name=brand_name)
    session.add(brand)
    try:
        session.commit()
        session.refresh(brand)
        logger.info(f"Created brand: {brand_name}")
        return brand
    except IntegrityError:
        session.rollback()
        return session.exec(select(Brand).where(Brand.name == brand_name)).one()


def migrate_product(
    session: Session, 
    variation_data: Dict[str, Any], 
    ai_data: Dict[str, Any],
    brand: Brand,
    super_category: SuperCategory,
    category: Category,
    seen_barcodes: Set[str]
) -> Optional[Product]:
    """Migrate a single product with its variation and AI data."""
    
    variation = variation_data.get("variation", {})
    price_info = variation.get("price", {})
    
    barcode = ai_data.get("barcode") if ai_data else None
    if barcode:
        barcode = barcode.strip()
        if not barcode:
            barcode = None
    
    if barcode:
        if barcode in seen_barcodes:
            logger.warning(f"Duplicate barcode {barcode} found in this session for '{variation.get('display_name')}'. Skipping.")
            return None
        
        existing_product = session.exec(select(Product).where(Product.barcode == barcode)).first()
        if existing_product:
            logger.info(f"Barcode {barcode} already exists in DB for product '{existing_product.display_name}'. Skipping.")
            return None
        
        seen_barcodes.add(barcode)
    
    veg_status = safe_enum(ai_data.get("veg_non_veg") if ai_data else None, VegStatus)
    processing_level = safe_enum(ai_data.get("processing_level") if ai_data else None, ProcessingLevel)
    
    product = Product(
        name=ai_data.get("product_name") if ai_data else variation.get("product_name_without_brand", ""),
        display_name=variation.get("display_name", ""),
        primary_source=DataSource.SWIGGY,
        primary_external_id=variation.get("id", ""),
        primary_external_variation_id=variation_data.get("parent_product", {}).get("product_id"),
        brand_id=brand.id,
        super_category_id=super_category.id,
        category_id=category.id,
        sub_category_l3=variation.get("category"), # Mapping product's 'category' to sub_category_l3
        sub_category_l4=variation.get("sub_category_l3"),
        sub_category_l5=variation.get("sub_category_l4"),
        mrp=safe_float(price_info.get("mrp")),
        store_price=safe_float(price_info.get("store_price")),
        offer_price=safe_float(price_info.get("offer_price")),
        discount_value=safe_float(price_info.get("discount_value")),
        unit_level_price=price_info.get("unit_level_price"),
        quantity=variation.get("quantity"),
        unit_of_measure=variation.get("unit_of_measure"),
        weight_in_grams=safe_float(variation.get("weight_in_grams")),
        volumetric_weight=safe_float(variation.get("volumetric_weight")),
        sku_quantity_with_combo=variation.get("sku_quantity_with_combo"),
        product_type=variation.get("scm_item_type"),
        filters_tag=variation.get("filters_tag"),
        barcode=barcode,
        veg_status=veg_status,
        health_rating=safe_int(ai_data.get("health_rating")) if ai_data else None,
        processing_level=processing_level,
        country_of_origin=ai_data.get("country_of_origin") if ai_data else None,
        net_quantity_value=safe_float(ai_data.get("net_quantity_value")) if ai_data else None,
        net_quantity_unit=ai_data.get("net_quantity_unit") if ai_data else None,
        nutrition_serving_value=safe_float(ai_data.get("nutrition_serving_value")) if ai_data else None,
        nutrition_serving_unit=ai_data.get("nutrition_serving_unit") if ai_data else None,
        approx_serves_per_pack=safe_int(ai_data.get("approx_serves_per_pack")) if ai_data else None,
        ingredients_string=ai_data.get("ingredients_string") if ai_data else None,
        storage_instructions=ai_data.get("storage_instructions") if ai_data else None,
        cooking_instructions=ai_data.get("cooking_instructions") if ai_data else None,
        allergens=json.dumps(ai_data.get("allergens", [])) if ai_data and ai_data.get("allergens") else None,
        certifications=json.dumps(ai_data.get("certifications", [])) if ai_data and ai_data.get("certifications") else None,
        positive_health_aspects=json.dumps(ai_data.get("positive_health_aspects", [])) if ai_data and ai_data.get("positive_health_aspects") else None,
        negative_health_aspects=json.dumps(ai_data.get("negative_health_aspects", [])) if ai_data and ai_data.get("negative_health_aspects") else None,
        preservatives=json.dumps(ai_data.get("preservatives", [])) if ai_data and ai_data.get("preservatives") else None,
        ins_numbers_found=json.dumps(ai_data.get("ins_numbers_found", [])) if ai_data and ai_data.get("ins_numbers_found") else None,
        additives=json.dumps(ai_data.get("additives", [])) if ai_data and ai_data.get("additives") else None,
        alarming_ingredients=json.dumps(ai_data.get("alarming_ingredients", [])) if ai_data and ai_data.get("alarming_ingredients") else None
    )
    
    try:
        session.add(product)
        session.commit()
        session.refresh(product)
        logger.info(f"Created product: {product.display_name}")
        return product
    except IntegrityError as e:
        session.rollback()
        logger.error(f"Error creating product {product.display_name}: {e}")
        return None


def migrate_product_images(session: Session, product: Product, variation_data: Dict[str, Any], brand_id: str, variation_id: str):
    """Migrate product images."""
    variation = variation_data.get("variation", {})
    images = variation.get("images", [])
    
    for i, image_catalog_path in enumerate(images):
        filename = Path(image_catalog_path).name
        image_path = f"swiggy/listings/{brand_id}/{variation_id}/images/{filename}"
        
        statement = select(ProductImage).where(
            ProductImage.product_id == product.id,
            ProductImage.filename == image_path
        )
        if session.exec(statement).first():
            continue
        
        product_image = ProductImage(
            product_id=product.id,
            filename=image_path,
            order_index=i,
            is_primary=(i == 0)
        )
        session.add(product_image)
    
    if images:
        try:
            session.commit()
        except IntegrityError as e:
            session.rollback()
            logger.error(f"Error committing images for {product.display_name}: {e}")


def migrate_nutrition_facts(session: Session, product: Product, ai_data: Dict[str, Any]):
    """Migrate nutrition facts for a product."""
    if not ai_data or not ai_data.get("nutrition_info_table"):
        return
    
    for item in ai_data["nutrition_info_table"]:
        if not isinstance(item, dict): continue
        session.add(NutritionFact(
            product_id=product.id,
            nutrient=item.get("nutrient", ""),
            value=safe_float(item.get("value")) or 0.0,
            unit=item.get("unit", ""),
            rda_percentage=safe_float(item.get("rda_percentage"))
        ))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()

def migrate_ingredients(session: Session, product: Product, ai_data: Dict[str, Any]):
    """Migrate ingredients for a product."""
    if not ai_data or not ai_data.get("parsed_ingredients"):
        return

    for i, item in enumerate(ai_data["parsed_ingredients"]):
        if not isinstance(item, dict): continue
        session.add(Ingredient(
            product_id=product.id,
            name=item.get("name", ""),
            percentage=safe_float(item.get("percentage")),
            is_alarming=item.get("is_alarming", False),
            alarming_reason=item.get("alarming_reason"),
            order_index=i,
            ins_numbers=json.dumps(item.get("ins_numbers", [])) if item.get("ins_numbers") else None,
            additives=json.dumps(item.get("additives", [])) if item.get("additives") else None
        ))
    try:
        session.commit()
    except IntegrityError:
        session.rollback()


def migrate_scraped_data():
    """Main migration function."""
    logger.info("Starting data migration...")
    create_db_and_tables()
    
    scraped_data_dir = Path("scraped_data")
    if not scraped_data_dir.exists():
        logger.error("scraped_data directory not found!")
        return
    
    stats = {"brands": 0, "products": 0, "skipped": 0, "errors": 0}
    seen_barcodes: Set[str] = set()
    
    with Session(engine) as session:
        super_category_map = migrate_super_categories(session)
        category_map = migrate_categories_and_build_map(session, super_category_map)
        
        listings_dir = scraped_data_dir / "swiggy" / "listings"
        if not listings_dir.exists():
            logger.error("swiggy/listings directory not found!")
            return
        
        for brand_dir in listings_dir.iterdir():
            if not brand_dir.is_dir(): continue
            
            try:
                brand_info = load_json_file(brand_dir / "brand_info.json")
                if not brand_info: continue

                brand = migrate_brand(session, brand_info)
                if not brand: continue
                stats["brands"] += 1
                
                for variation_dir in brand_dir.iterdir():
                    if not variation_dir.is_dir(): continue
                    
                    try:
                        data_file = variation_dir / "data.json"
                        ai_file = variation_dir / "parsed_ai.json"
                        if not data_file.exists(): continue

                        variation_data = load_json_file(data_file)
                        ai_data = load_json_file(ai_file) if ai_file.exists() else {}
                        if not isinstance(variation_data, dict): continue
                        
                        variation = variation_data.get("variation", {})
                        product_category_name = variation.get("super_category")
                        
                        if not product_category_name:
                            logger.warning(f"No 'super_category' field for {variation_dir}. Skipping.")
                            stats["skipped"] += 1
                            continue

                        category = category_map.get(product_category_name)
                        super_category = None

                        if category:
                            super_category = session.get(SuperCategory, category.super_category_id)
                        else:
                            logger.warning(f"Category '{product_category_name}' not in map. Assigning to 'Uncategorized'.")
                            uncategorized_sc_name = "Uncategorized"
                            super_category = super_category_map.get(uncategorized_sc_name)
                            if not super_category:
                                super_category = SuperCategory(name=uncategorized_sc_name)
                                session.add(super_category)
                                try:
                                    session.commit()
                                    session.refresh(super_category)
                                    super_category_map[uncategorized_sc_name] = super_category
                                except IntegrityError:
                                    session.rollback()
                                    super_category = session.exec(select(SuperCategory).where(SuperCategory.name == uncategorized_sc_name)).one()
                            
                            category = session.exec(select(Category).where(Category.name == product_category_name, Category.super_category_id == super_category.id)).first()
                            if not category:
                                category = Category(name=product_category_name, super_category_id=super_category.id)
                                session.add(category)
                                try:
                                    session.commit()
                                    session.refresh(category)
                                    category_map[product_category_name] = category
                                except IntegrityError:
                                    session.rollback()
                                    category = session.exec(select(Category).where(Category.name == product_category_name, Category.super_category_id == super_category.id)).one()

                        if not super_category or not category:
                            logger.error(f"Could not determine category/super-category for {variation_dir}. Skipping.")
                            stats["skipped"] += 1
                            continue

                        product = migrate_product(
                            session, variation_data, ai_data, brand, super_category, category, seen_barcodes
                        )
                        
                        if product:
                            stats["products"] += 1
                            migrate_product_images(session, product, variation_data, brand_dir.name, variation_dir.name)
                            migrate_nutrition_facts(session, product, ai_data)
                            migrate_ingredients(session, product, ai_data)
                        else:
                            stats["skipped"] += 1
                        
                    except Exception as e:
                        logger.error(f"Error processing variation {variation_dir}: {e}", exc_info=True)
                        stats["errors"] += 1
            
            except Exception as e:
                logger.error(f"Error processing brand {brand_dir}: {e}", exc_info=True)
                stats["errors"] += 1

    logger.info("\nMigration completed!")
    logger.info(f"Super categories: {len(super_category_map)}")
    logger.info(f"Categories: {len(category_map)}")
    logger.info(f"Brands migrated: {stats['brands']}")
    logger.info(f"Products migrated: {stats['products']}")
    logger.info(f"Products skipped: {stats['skipped']}")
    logger.info(f"Errors: {stats['errors']}")


if __name__ == "__main__":
    migrate_scraped_data()