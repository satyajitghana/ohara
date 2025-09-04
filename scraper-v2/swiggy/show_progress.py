#!/usr/bin/env python3
"""
Show current scraping progress across all steps
"""

import json
from pathlib import Path
from collections import defaultdict
from utils.common import load_config, get_existing_pages


def analyze_progress():
    """Analyze and display current scraping progress"""
    config = load_config()
    responses_folder = Path(config["responses_folder"])
    
    # Folder paths
    home_file = responses_folder / "home.json"
    categories_folder = responses_folder / "raw" / "categories"
    categories_all_folder = responses_folder / "raw" / "categories-all"
    discovered_folder = responses_folder / "raw" / "discovered_categories"
    errors_folder = responses_folder / "errors"
    
    print("🚀 Swiggy Scraper Progress Report")
    print("=" * 50)
    
    # Step 1: Home categories
    if home_file.exists():
        with open(home_file, 'r') as f:
            home_data = json.load(f)
            total_home_categories = home_data.get("total_categories", 0)
            print(f"📊 Step 1 - Home Categories: {total_home_categories} found")
    else:
        print("❌ Step 1 - Home categories not found. Run step1 first.")
        return
    
    # Step 2: Category listings
    step2_categories = defaultdict(list)
    if categories_folder.exists():
        for file_path in categories_folder.glob("*_page_*.json"):
            category_name = file_path.stem.split("_page_")[0]
            page_no = int(file_path.stem.split("_page_")[1])
            step2_categories[category_name].append(page_no)
    
    print(f"📦 Step 2 - Category Listings:")
    print(f"   Categories started: {len(step2_categories)}")
    
    total_step2_pages = sum(len(pages) for pages in step2_categories.values())
    print(f"   Total pages scraped: {total_step2_pages}")
    
    # Show top categories by pages
    if step2_categories:
        top_categories = sorted(step2_categories.items(), key=lambda x: len(x[1]), reverse=True)[:5]
        print(f"   Top categories by pages:")
        for cat_name, pages in top_categories:
            print(f"     - {cat_name}: {len(pages)} pages")
    
    # Discovered categories
    discovered_count = 0
    if discovered_folder.exists():
        discovered_files = list(discovered_folder.glob("DISCOVERED_*.json"))
        for file_path in discovered_files:
            try:
                with open(file_path, 'r') as f:
                    data = json.load(f)
                    discovered_count += data.get("metadata", {}).get("total_discovered", 0)
            except:
                pass
    
    print(f"🔍 Discovered Items: {discovered_count} total")
    
    # Step 3: All categories
    all_categories = defaultdict(list)
    if categories_all_folder.exists():
        for file_path in categories_all_folder.glob("*_page_*.json"):
            category_name = file_path.stem.split("_page_")[0]
            page_no = int(file_path.stem.split("_page_")[1])
            all_categories[category_name].append(page_no)
    
    print(f"🎯 Categories-All (Final Results):")
    print(f"   Unique categories: {len(all_categories)}")
    
    total_all_pages = sum(len(pages) for pages in all_categories.values())
    print(f"   Total pages: {total_all_pages}")
    
    # Show top categories by pages
    if all_categories:
        top_all_categories = sorted(all_categories.items(), key=lambda x: len(x[1]), reverse=True)[:5]
        print(f"   Top categories by pages:")
        for cat_name, pages in top_all_categories:
            print(f"     - {cat_name}: {len(pages)} pages (pages: {sorted(pages)})")
    
    # Errors
    error_count = 0
    if errors_folder.exists():
        error_count = len(list(errors_folder.glob("ERROR_*.json")))
    
    print(f"❌ Errors: {error_count} total")
    
    # Overall progress
    print(f"\n🎯 OVERALL PROGRESS:")
    home_categories = home_data.get("categories", [])
    home_category_names = {cat["category_name"] for cat in home_categories}
    scraped_category_names = set(all_categories.keys())
    
    completion_rate = len(scraped_category_names) / len(home_category_names) * 100 if home_category_names else 0
    print(f"   Completion rate: {completion_rate:.1f}% ({len(scraped_category_names)}/{len(home_category_names)})")
    
    # Missing categories
    missing_categories = home_category_names - scraped_category_names
    if missing_categories:
        print(f"   Missing categories: {len(missing_categories)}")
        for cat in sorted(missing_categories)[:10]:  # Show first 10
            print(f"     - {cat}")
        if len(missing_categories) > 10:
            print(f"     ... and {len(missing_categories) - 10} more")


if __name__ == "__main__":
    analyze_progress()
