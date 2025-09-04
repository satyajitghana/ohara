#!/usr/bin/env python3
"""
Step 4: Product Extractor
Extracts products from all category and filter data files sequentially.
Saves products in responses-v4/products/<product_id>/data.json structure.
Avoids duplicates and combines categories/filters for products found in multiple places.
"""

import asyncio
import sys
import re
import json
from pathlib import Path
from typing import Dict, Any, List, Set, Optional

# Add the current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from utils.common import (
    load_config, 
    save_json, 
    ensure_directory
)


def is_combo_product(variation: Dict[str, Any]) -> bool:
    """
    Check if a product variation is a combo/multi-pack that should be excluded.
    Returns True if it's a combo that should be excluded.
    """
    quantity = variation.get('quantity', '').lower()
    sku_quantity = variation.get('sku_quantity_with_combo', '').lower()
    
    # Check for pieces (indicates multi-pack)
    if 'pieces' in quantity or 'piece' in quantity:
        return True
    
    # Check for "combo" in quantity
    if 'combo' in quantity:
        return True
    
    # Check for "x" indicating combo (e.g., "400 g x 2")
    if ' x ' in sku_quantity or ' X ' in sku_quantity:
        return True
    
    # Additional combo patterns
    combo_patterns = [
        r'\d+\s*x\s*\d+',  # "2x500g", "3 x 400g"
        r'pack\s*of\s*\d+',  # "pack of 2", "pack of 3"
        r'\d+\s*pack',  # "2 pack", "3pack"
        r'combo',  # any combo text
    ]
    
    combined_text = f"{quantity} {sku_quantity}"
    for pattern in combo_patterns:
        if re.search(pattern, combined_text, re.IGNORECASE):
            return True
    
    return False


def get_non_combo_variation(variations: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Get the first variation that is not a combo/multi-pack.
    Returns None if all variations are combos.
    """
    for variation in variations:
        if not is_combo_product(variation):
            return variation
    return None


def extract_product_data(product_item: Dict[str, Any], category_name: str, filter_name: str = None, filter_id: str = None) -> Optional[Dict[str, Any]]:
    """
    Extract and structure product data from a product item.
    Returns None if the product should be excluded.
    """
    variations = product_item.get('variations', [])
    if not variations:
        return None
    
    # Get the first non-combo variation
    variation = get_non_combo_variation(variations)
    if not variation:
        return None  # All variations are combos, skip this product
    
    # Extract required fields
    product_data = {
        'product_id': variation.get('id'),
        'display_name': product_item.get('display_name'),
        'product_name_without_brand': variation.get('product_name_without_brand'),
        'brand': variation.get('brand'),
        'brand_id': variation.get('brand_id'),
        'images': variation.get('images', []),
        'images_v2': variation.get('images_v2', []),
        'price': {
            'mrp': variation.get('price', {}).get('mrp'),
            'store_price': variation.get('price', {}).get('store_price'),
            'offer_price': variation.get('price', {}).get('offer_price'),
            'unit_level_price': variation.get('price', {}).get('unit_level_price', '')
        },
        'quantity': variation.get('quantity'),
        'sku_quantity_with_combo': variation.get('sku_quantity_with_combo'),
        'unit_of_measure': variation.get('unit_of_measure'),
        'tags': variation.get('tags'),
        'weight_in_grams': variation.get('weight_in_grams'),
        'volumetric_weight': variation.get('volumetric_weight'),
        'sub_category_type': variation.get('sub_category_type'),
        'category': variation.get('category'),
        'super_category': variation.get('super_category'),
        'sub_category_l3': variation.get('sub_category_l3'),
        'sub_category_l4': variation.get('sub_category_l4'),
        'sub_category_l5': variation.get('sub_category_l5'),
        'filters_tag': variation.get('filters_tag'),
        'short_description': variation.get('meta', {}).get('short_description', ''),
        
        # Swiggy-specific fields
        'swiggy_data': {
            'category_id': variation.get('category_id'),
            'category_name': category_name,
            'filter_id': filter_id,
            'filter_name': filter_name,
            'brand_id': variation.get('brand_id'),
            'store_id': variation.get('store_id'),
            'spin': variation.get('spin')
        },
        
        # Track categories and filters this product appears in
        'categories': [category_name],
        'filters': [filter_name] if filter_name else []
    }
    
    return product_data


def merge_product_data(existing_data: Dict[str, Any], new_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Merge new product data with existing data, combining categories and filters.
    """
    # Add new category if not already present
    if new_data['swiggy_data']['category_name'] not in existing_data['categories']:
        existing_data['categories'].append(new_data['swiggy_data']['category_name'])
    
    # Add new filter if not already present
    if new_data['swiggy_data']['filter_name'] and new_data['swiggy_data']['filter_name'] not in existing_data['filters']:
        existing_data['filters'].append(new_data['swiggy_data']['filter_name'])
    
    # Update swiggy_data to include multiple sources
    if 'sources' not in existing_data['swiggy_data']:
        existing_data['swiggy_data']['sources'] = []
    
    source_info = {
        'category_id': new_data['swiggy_data']['category_id'],
        'category_name': new_data['swiggy_data']['category_name'],
        'filter_id': new_data['swiggy_data']['filter_id'],
        'filter_name': new_data['swiggy_data']['filter_name']
    }
    
    # Check if this source already exists
    source_exists = False
    for existing_source in existing_data['swiggy_data']['sources']:
        if (existing_source['category_name'] == source_info['category_name'] and 
            existing_source['filter_name'] == source_info['filter_name']):
            source_exists = True
            break
    
    if not source_exists:
        existing_data['swiggy_data']['sources'].append(source_info)
    
    return existing_data


def process_product_widgets(widgets: List[Dict[str, Any]], category_name: str, filter_name: str = None, filter_id: str = None) -> List[Dict[str, Any]]:
    """
    Process widgets to extract products from PRODUCT_LIST widgets.
    """
    products = []
    
    for widget in widgets:
        widget_info = widget.get('widgetInfo', {})
        if widget_info.get('widgetType') == 'PRODUCT_LIST':
            widget_data = widget.get('data', [])
            
            for product_item in widget_data:
                product_data = extract_product_data(product_item, category_name, filter_name, filter_id)
                if product_data:
                    products.append(product_data)
    
    return products


def load_page_data(page_file: Path) -> Optional[Dict[str, Any]]:
    """Load and return page data from JSON file."""
    try:
        with open(page_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading page data from {page_file}: {e}")
        return None


def process_category_pages(category_dir: Path, category_name: str) -> List[Dict[str, Any]]:
    """
    Process all pages for a category to extract products.
    """
    products = []
    
    # Process main category pages
    page_files = sorted(category_dir.glob(f"{category_dir.name}_page_*.json"))
    
    for page_file in page_files:
        print(f"  📄 Processing category page: {page_file.name}")
        page_data = load_page_data(page_file)
        
        if not page_data:
            continue
        
        # Extract category name from first page
        if page_file.name.endswith('_page_0.json'):
            data_section = page_data.get('data', {})
            selected_category_name = data_section.get('selectedCategoryName')
            if selected_category_name:
                category_name = selected_category_name
        
        # Process widgets
        widgets = page_data.get('data', {}).get('widgets', [])
        if widgets:
            page_products = process_product_widgets(widgets, category_name)
            products.extend(page_products)
            print(f"    ✅ Found {len(page_products)} products in {page_file.name}")
    
    return products


def process_filter_pages(filter_dir: Path, category_name: str, filter_name: str, filter_id: str) -> List[Dict[str, Any]]:
    """
    Process all pages for a filter to extract products.
    """
    products = []
    
    # Process filter pages
    page_files = sorted(filter_dir.glob(f"{filter_dir.name}_page_*.json"))
    
    for page_file in page_files:
        print(f"    📄 Processing filter page: {page_file.name}")
        page_data = load_page_data(page_file)
        
        if not page_data:
            continue
        
        # Process widgets
        widgets = page_data.get('data', {}).get('widgets', [])
        if widgets:
            page_products = process_product_widgets(widgets, category_name, filter_name, filter_id)
            products.extend(page_products)
            print(f"      ✅ Found {len(page_products)} products in {page_file.name}")
    
    return products


def save_product_data(product: Dict[str, Any], products_dir: Path) -> bool:
    """
    Save product data to products directory structure.
    Returns True if saved, False if merged with existing.
    """
    product_id = product['product_id']
    if not product_id:
        print(f"⚠️ Skipping product with no ID: {product.get('display_name', 'Unknown')}")
        return False
    
    product_dir = products_dir / product_id
    ensure_directory(product_dir)
    
    product_file = product_dir / "data.json"
    
    # Check if product already exists
    if product_file.exists():
        try:
            with open(product_file, 'r', encoding='utf-8') as f:
                existing_data = json.load(f)
            
            # Merge with existing data
            merged_data = merge_product_data(existing_data, product)
            save_json(merged_data, product_file)
            print(f"  🔄 Updated existing product: {product_id}")
            return False
        except Exception as e:
            print(f"❌ Error loading existing product {product_id}: {e}")
            return False
    else:
        # Save new product
        save_json(product, product_file)
        print(f"  💾 Saved new product: {product_id}")
        return True


def process_single_category(category_dir: Path, products_dir: Path) -> Dict[str, int]:
    """
    Process a single category and all its filters.
    Returns statistics dictionary.
    """
    category_name = category_dir.name.replace('_', ' ')
    print(f"\n🗂️ Processing category: {category_name}")
    
    stats = {
        'category_products': 0,
        'filter_products': 0,
        'new_products': 0,
        'updated_products': 0,
        'filters_processed': 0
    }
    
    # Process main category pages
    category_products = process_category_pages(category_dir, category_name)
    stats['category_products'] = len(category_products)
    
    # Save category products
    for product in category_products:
        if save_product_data(product, products_dir):
            stats['new_products'] += 1
        else:
            stats['updated_products'] += 1
    
    # Process filters
    filters_dir = category_dir / "filters"
    if filters_dir.exists():
        filter_dirs = [d for d in filters_dir.iterdir() if d.is_dir()]
        stats['filters_processed'] = len(filter_dirs)
        
        for filter_dir in filter_dirs:
            filter_name = filter_dir.name.replace('_', ' ')
            print(f"  🔍 Processing filter: {filter_name}")
            
            # Try to get filter ID from one of the page files
            filter_id = None
            page_files = list(filter_dir.glob("*_page_0.json"))
            if page_files:
                page_data = load_page_data(page_files[0])
                if page_data:
                    selected_filter_id = page_data.get('data', {}).get('selectedFilterId')
                    if selected_filter_id:
                        filter_id = selected_filter_id
            
            filter_products = process_filter_pages(filter_dir, category_name, filter_name, filter_id)
            stats['filter_products'] += len(filter_products)
            
            # Save filter products
            for product in filter_products:
                if save_product_data(product, products_dir):
                    stats['new_products'] += 1
                else:
                    stats['updated_products'] += 1
    
    return stats


def main():
    """Main function to extract products from all categories and filters."""
    print("🚀 Starting Product Extraction (Step 4)...")
    
    try:
        # Load configuration
        config = load_config()
        responses_dir = Path(config['output']['base_directory'])
        
        if not responses_dir.exists():
            print(f"❌ Output directory not found: {responses_dir}")
            print("   Please run previous steps first.")
            return 1
        
        # Define target categories
        target_categories = [
            "Atta_Rice_and_Dal",
            "Biscuits_and_Cakes", 
            "Cereals_and_Breakfast",
            "Chips_and_Namkeens",
            "Chocolates",
            "Cold_Drinks_and_Juices",
            "Dairy_Bread_and_Eggs",
            "Dry_Fruits_and_Seeds_Mix",
            "Frozen_Food",
            "Ice_Creams_and_Frozen_Desserts",
            "Meat_and_Seafood",
            "Noodles_Pasta_Vermicelli",
            "Oils_and_Ghee",
            "Protein_and_Supplements",
            "Sauces_and_Spreads",
            "Sweets",
            "Tea_Coffee_and_Milk_drinks"
        ]
        
        # Setup directories
        categories_subdir = config['output']['categories_subdirectory']
        categories_base_dir = responses_dir / categories_subdir
        products_dir = responses_dir / "products"
        ensure_directory(products_dir)
        
        if not categories_base_dir.exists():
            print(f"❌ Categories directory not found: {categories_base_dir}")
            return 1
        
        # Process each target category sequentially
        total_stats = {
            'categories_processed': 0,
            'category_products': 0,
            'filter_products': 0,
            'new_products': 0,
            'updated_products': 0,
            'filters_processed': 0
        }
        
        for category_name in target_categories:
            category_dir = categories_base_dir / category_name
            
            if not category_dir.exists():
                print(f"⚠️ Category directory not found: {category_dir}")
                continue
            
            # Process category
            stats = process_single_category(category_dir, products_dir)
            
            # Update totals
            total_stats['categories_processed'] += 1
            total_stats['category_products'] += stats['category_products']
            total_stats['filter_products'] += stats['filter_products']
            total_stats['new_products'] += stats['new_products']
            total_stats['updated_products'] += stats['updated_products']
            total_stats['filters_processed'] += stats['filters_processed']
            
            print(f"  📊 Category {category_name}: {stats['new_products']} new, {stats['updated_products']} updated products")
        
        # Print final summary
        print(f"\n🎉 Product extraction completed!")
        print(f"📊 Final Statistics:")
        print(f"   Categories processed: {total_stats['categories_processed']}")
        print(f"   Filters processed: {total_stats['filters_processed']}")
        print(f"   Products from categories: {total_stats['category_products']}")
        print(f"   Products from filters: {total_stats['filter_products']}")
        print(f"   New products saved: {total_stats['new_products']}")
        print(f"   Existing products updated: {total_stats['updated_products']}")
        print(f"   Total unique products: {total_stats['new_products'] + total_stats['updated_products']}")
        print(f"📁 Products saved in: {products_dir}")
        
        return 0
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
