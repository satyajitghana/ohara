#!/usr/bin/env python3
"""
Step 3: Scrape products from discovered categories with pagination support
This script reads discovered categories from step2 and scrapes all products with pagination.
Copies Step 2 results to categories-all and avoids duplicate scraping.
Fully resumable - can be stopped and restarted to continue where it left off.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Set

# Import from utils
from utils.common import (
    load_config, sanitize_filename, scrape_category_with_pagination,
    setup_base_folders, copy_categories_to_all_folder, is_category_fully_scraped,
    get_existing_pages
)


def load_discovered_categories(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load all discovered categories from step2 results"""
    responses_folder = Path(config["responses_folder"])
    discovered_folder = responses_folder / "raw" / "discovered_categories"
    
    all_discovered = []
    discovered_files = list(discovered_folder.glob("DISCOVERED_*.json"))
    
    print(f"Found {len(discovered_files)} discovered category files")
    
    for file_path in discovered_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                discovered_items = data.get("discovered_items", [])
                all_discovered.extend(discovered_items)
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    return all_discovered


def setup_step3_folders(config: Dict[str, Any]):
    """Create Step 3 specific folders"""
    responses_folder, categories_folder, categories_all_folder, discovered_folder, errors_folder = setup_base_folders(config)
    
    print(f"✓ Created folder structure:")
    print(f"   Categories (Step 2 input): {categories_folder}")
    print(f"   Categories-All (Output): {categories_all_folder}")
    print(f"   Discovered (raw): {discovered_folder}")
    print(f"   Errors: {errors_folder}")
    
    return categories_folder, categories_all_folder, discovered_folder, errors_folder


def get_unique_discovered_categories(discovered_items: List[Dict[str, Any]], categories_all_folder: Path) -> List[Dict[str, Any]]:
    """Get unique discovered categories to scrape, avoiding duplicates and already scraped ones"""
    seen_categories = set()
    unique_categories = []
    
    for item in discovered_items:
        if item["type"] != "related_category":
            continue
            
        category_name = item["displayName"]
        category_id = item["id"]
        
        # Skip if we've already seen this category (by ID)
        if category_id in seen_categories:
            continue
            
        # Skip if already fully scraped in categories-all
        if is_category_fully_scraped(categories_all_folder, category_name):
            print(f"  ⏭️  {category_name} already fully scraped, skipping...")
            continue
            
        seen_categories.add(category_id)
        unique_categories.append({
            "id": category_id,
            "category_name": category_name,
            "productCount": item.get("productCount", 0),
            "imageId": item.get("imageId", ""),
            "ageConsentRequired": item.get("ageConsentRequired", False)
        })
    
    return unique_categories


def show_resume_info(categories_all_folder: Path, category_name: str):
    """Show resume information for a category"""
    existing_pages = get_existing_pages(categories_all_folder, category_name)
    if existing_pages:
        print(f"  🔄 Resuming {category_name} (found existing pages: {existing_pages})")
    else:
        print(f"  🆕 Starting fresh scrape for {category_name}")


def main():
    """Main function"""
    print("🚀 Starting Step 3: Scrape Discovered Categories with Pagination")
    print("=" * 75)
    
    try:
        # Load config and discovered categories
        config = load_config()
        print("✓ Loaded configuration")
        
        discovered_items = load_discovered_categories(config)
        print(f"✓ Loaded {len(discovered_items)} discovered items from step2")
        
        # Setup folders
        categories_folder, categories_all_folder, discovered_folder, errors_folder = setup_step3_folders(config)
        
        # Step 1: Copy Step 2 results to categories-all folder
        print(f"\n📋 Copying Step 2 results to categories-all folder...")
        copied_count = copy_categories_to_all_folder(categories_folder, categories_all_folder)
        
        # Step 2: Get unique discovered categories to scrape
        unique_categories = get_unique_discovered_categories(discovered_items, categories_all_folder)
        print(f"✓ Found {len(unique_categories)} unique discovered categories to scrape (after deduplication)")
        
        if not unique_categories:
            print("⚠️  No new discovered categories to scrape!")
            print("   All discovered categories have already been scraped.")
            return
        
        # Track progress
        successful_categories = 0
        failed_categories = 0
        total_pages_scraped = 0
        total_products_scraped = 0
        
        # Process each unique discovered category
        for i, category in enumerate(unique_categories, 1):
            print(f"\n📦 Processing discovered category {i}/{len(unique_categories)}: {category['category_name']}")
            print(f"   Expected products: {category['productCount']}")
            
            # Show resume info
            show_resume_info(categories_all_folder, category["category_name"])
            
            try:
                # Scrape all pages for this discovered category
                pages, products = scrape_category_with_pagination(
                    config, category, categories_all_folder, errors_folder, resume=True
                )
                
                if pages > 0:
                    successful_categories += 1
                    total_pages_scraped += pages
                    total_products_scraped += products
                    print(f"  ✅ Successfully scraped {pages} pages with {products} products")
                else:
                    failed_categories += 1
                    print(f"  ❌ Failed to scrape any pages")
                    
            except Exception as e:
                print(f"  ❌ Failed to process {category['category_name']}: {e}")
                failed_categories += 1
                continue
        
        # Final summary
        print("\n" + "=" * 75)
        print("📊 FINAL SUMMARY:")
        print(f"   📋 Categories copied from Step 2: {copied_count}")
        print(f"   🔍 Discovered categories processed: {len(unique_categories)}")
        print(f"   ✅ Successful categories: {successful_categories}")
        print(f"   ❌ Failed categories: {failed_categories}")
        print(f"   📄 Total pages scraped: {total_pages_scraped}")
        print(f"   🛍️  Total products scraped: {total_products_scraped}")
        print(f"   📁 All categories saved in: {categories_all_folder}")
        print(f"   ❌ Errors saved in: {errors_folder}")
        
        # Show total categories in categories-all
        all_category_files = list(categories_all_folder.glob("*_page_0.json"))
        total_unique_categories = len(set(f.stem.split("_page_")[0] for f in all_category_files))
        
        print(f"\n🎯 OVERALL PROGRESS:")
        print(f"   📊 Total unique categories in categories-all: {total_unique_categories}")
        print(f"   📄 Total pages across all categories: {len(list(categories_all_folder.glob('*.json')))}")
        
        if successful_categories > 0:
            print("\n✅ Step 3 completed!")
            print(f"🎉 Successfully scraped {total_products_scraped} products from {successful_categories} discovered categories!")
        else:
            print("\n✅ Step 3 completed - no new categories to scrape!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
