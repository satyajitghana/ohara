#!/usr/bin/env python3
"""
Step 2: Get listings for each category from Swiggy with pagination support
This script reads the categories from step1 and fetches all pages for each category.
Fully resumable - can be stopped and restarted to continue where it left off.
"""

import json
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any

# Import from utils
from utils.common import (
    load_config, sanitize_filename, scrape_category_with_pagination,
    setup_base_folders, exponential_backoff, is_rate_limited
)


def load_categories(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load categories from step1 results"""
    responses_folder = config["responses_folder"]
    categories_path = Path(responses_folder) / "home.json"
    if not categories_path.exists():
        raise FileNotFoundError(f"home.json not found in {responses_folder}. Please run step1 first.")
    
    with open(categories_path, 'r') as f:
        data = json.load(f)
        return data.get("categories", [])


def setup_step2_folders(config: Dict[str, Any]):
    """Create Step 2 specific folders"""
    responses_folder, categories_folder, categories_all_folder, discovered_folder, errors_folder = setup_base_folders(config)
    
    print(f"✓ Created folder structure:")
    print(f"   Categories (Step 2 output): {categories_folder}")
    print(f"   Categories-All (Final output): {categories_all_folder}")
    print(f"   Discovered (raw): {discovered_folder}")
    print(f"   Errors: {errors_folder}")
    
    return categories_folder, categories_all_folder, discovered_folder, errors_folder


def extract_discovered_categories(response_data: Dict[str, Any], source_category: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract newly discovered related categories and filters from response"""
    discovered = []
    
    if "data" not in response_data:
        return discovered
    
    data = response_data["data"]
    
    # Extract related categories (these are the categories in the sidebar - many-to-many relationship)
    categories = data.get("categories", [])
    for cat in categories:
        discovered.append({
            "type": "related_category",
            "id": cat.get("id", ""),
            "displayName": cat.get("displayName", ""),
            "productCount": cat.get("productCount", 0),
            "imageId": cat.get("imageId", ""),
            "ageConsentRequired": cat.get("ageConsentRequired", False),
            "found_via_category": source_category["category_name"],
            "source_category_id": source_category["id"]
        })
    
    # Extract filters/subcategories (these are filters within the category)
    filters = data.get("filters", [])
    for filter_item in filters:
        discovered.append({
            "type": "category_filter",
            "id": filter_item.get("id", ""),
            "name": filter_item.get("name", ""),
            "productCount": filter_item.get("productCount", 0),
            "imageId": filter_item.get("imageId", ""),
            "filter_type": filter_item.get("type", ""),
            "parent_category": source_category["category_name"],
            "parent_category_id": source_category["id"]
        })
    
    return discovered


def save_discovered_categories(discovered_folder: Path, category: Dict[str, Any], discovered_items: List[Dict[str, Any]]):
    """Save discovered related categories and filters for a category"""
    if not discovered_items:
        return None
        
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create safe filename
    category_name = sanitize_filename(category["category_name"])
    filename = f"DISCOVERED_{category_name}_{timestamp}.json"
    
    discovered_file = discovered_folder / filename
    
    # Separate by type for better analysis
    related_categories = [item for item in discovered_items if item["type"] == "related_category"]
    category_filters = [item for item in discovered_items if item["type"] == "category_filter"]
    
    # Create summary
    summary_data = {
        "metadata": {
            "source_category_id": category["id"],
            "source_category_name": category["category_name"],
            "source_category_group": category["category_group"],
            "timestamp": timestamp,
            "scraped_at": datetime.now().isoformat(),
            "total_discovered": len(discovered_items),
            "related_categories_count": len(related_categories),
            "category_filters_count": len(category_filters)
        },
        "discovered_items": discovered_items,
        "summary": {
            "related_categories": related_categories,
            "category_filters": category_filters
        }
    }
    
    with open(discovered_file, 'w') as f:
        json.dump(summary_data, f, indent=2)
    
    print(f"  🔍 Discovered {len(discovered_items)} items ({len(related_categories)} related categories, {len(category_filters)} filters), saved to: {discovered_file}")
    return discovered_file


def is_category_started(categories_folder: Path, category_name: str) -> bool:
    """Check if a category has any pages scraped"""
    from utils.common import get_existing_pages
    existing_pages = get_existing_pages(categories_folder, category_name)
    return len(existing_pages) > 0


def main():
    """Main function"""
    print("🚀 Starting Step 2: Get Category Listings from Swiggy (with Pagination)")
    print("=" * 70)
    
    try:
        # Load config and categories
        config = load_config()
        print("✓ Loaded configuration")
        
        categories = load_categories(config)
        print(f"✓ Loaded {len(categories)} categories from step1")
        
        # Setup folders
        categories_folder, categories_all_folder, discovered_folder, errors_folder = setup_step2_folders(config)
        
        # Track progress
        successful_categories = 0
        failed_categories = 0
        skipped_categories = 0
        total_pages_scraped = 0
        total_products_scraped = 0
        total_discovered = 0
        
        # Process each category
        for i, category in enumerate(categories, 1):
            print(f"\n📦 Processing category {i}/{len(categories)}: {category['category_name']}")
            print(f"   Group: {category['category_group']}")
            
            # Check if category has been started
            if is_category_started(categories_folder, category["category_name"]):
                from utils.common import get_existing_pages
                existing_pages = get_existing_pages(categories_folder, category["category_name"])
                print(f"  🔄 Resuming category (found existing pages: {existing_pages})")
            
            try:
                # Scrape all pages for this category
                pages, products = scrape_category_with_pagination(
                    config, category, categories_folder, errors_folder, resume=True
                )
                
                if pages > 0:
                    successful_categories += 1
                    total_pages_scraped += pages
                    total_products_scraped += products
                    
                    # For the first page, extract discovered categories
                    try:
                        category_name = sanitize_filename(category["category_name"])
                        first_page_file = categories_folder / f"{category_name}_page_0.json"
                        
                        if first_page_file.exists():
                            with open(first_page_file, 'r') as f:
                                page_data = json.load(f)
                                response_data = page_data.get("raw_response", {})
                                
                                # Extract discovered categories from first page
                                discovered_items = extract_discovered_categories(response_data, category)
                                if discovered_items:
                                    save_discovered_categories(discovered_folder, category, discovered_items)
                                    total_discovered += len(discovered_items)
                    except Exception as e:
                        print(f"  ⚠️  Warning: Could not extract discovered categories: {e}")
                    
                    print(f"  ✅ Successfully scraped {pages} pages with {products} products")
                else:
                    failed_categories += 1
                    print(f"  ❌ Failed to scrape any pages")
                    
            except Exception as e:
                print(f"  ❌ Failed to process {category['category_name']}: {e}")
                failed_categories += 1
                continue
        
        # Final summary
        print("\n" + "=" * 70)
        print("📊 FINAL SUMMARY:")
        print(f"   Total categories: {len(categories)}")
        print(f"   ✅ Successful categories: {successful_categories}")
        print(f"   ❌ Failed categories: {failed_categories}")
        print(f"   ⏭️  Skipped categories: {skipped_categories}")
        print(f"   📄 Total pages scraped: {total_pages_scraped}")
        print(f"   🛍️  Total products scraped: {total_products_scraped}")
        print(f"   🔍 Total related categories/filters discovered: {total_discovered}")
        print(f"   📁 Pages saved in: {categories_folder}")
        print(f"   🔍 Discovered categories in: {discovered_folder}")
        print(f"   ❌ Errors saved in: {errors_folder}")
        
        if successful_categories > 0:
            print("\n✅ Step 2 completed!")
            print(f"🎉 Successfully scraped {total_products_scraped} products from {successful_categories} categories!")
            if total_discovered > 0:
                print(f"🔍 Bonus: Discovered {total_discovered} related categories and filters for Step 3!")
        else:
            print("\n❌ Step 2 failed - no successful category scrapes")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
