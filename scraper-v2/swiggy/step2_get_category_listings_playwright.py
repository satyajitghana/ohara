#!/usr/bin/env python3
"""
Step 2 (Playwright): Get listings for each category from Swiggy with pagination support
This script reads the categories from step1 and fetches all pages for each category using Playwright.
Fully resumable - can be stopped and restarted to continue where it left off.
Supports parallel processing of categories.
"""

import asyncio
import json
import re
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
from urllib.parse import urlencode, unquote
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

# Import from utils
from utils.common import (
    load_config, sanitize_filename, setup_base_folders
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
    
    # Create debug folder
    debug_folder = Path(config["responses_folder"]) / "debug"
    debug_folder.mkdir(exist_ok=True)
    
    print(f"✓ Created folder structure:")
    print(f"   Categories (Step 2 output): {categories_folder}")
    print(f"   Categories-All (Final output): {categories_all_folder}")
    print(f"   Discovered (raw): {discovered_folder}")
    print(f"   Errors: {errors_folder}")
    print(f"   Debug: {debug_folder}")
    
    return categories_folder, categories_all_folder, discovered_folder, errors_folder, debug_folder


def parse_deeplink_params(deeplink: str) -> Dict[str, str]:
    """Extract parameters from Swiggy deeplink URL, handling age consent wrappers."""
    if deeplink.startswith("swiggy://ageConsent"):
        if "url=" in deeplink:
            encoded_url = deeplink.split("url=", 1)[1]
            deeplink = unquote(encoded_url)  # decode the inner url
    
    params = {}
    if "?" in deeplink:
        query_part = deeplink.split("?", 1)[1]
        for param_pair in query_part.split("&"):
            if "=" in param_pair:
                key, value = param_pair.split("=", 1)
                params[key] = value
    return params


def get_category_url(category: Dict[str, Any], page_offset: int = 0) -> str:
    """Generates a Swiggy Instamart category URL from a category object's deeplink with pagination."""
    base_url = "https://www.swiggy.com/instamart/category-listing"
    
    # Extract params from the authoritative deeplink
    params = parse_deeplink_params(category["deeplink"])
    
    # Ensure custom_back is present as it seems to be needed for web view
    params.setdefault("custom_back", "true")
    
    # Always set the offset to ensure we override the deeplink's value and handle pagination correctly
    params["offset"] = str(page_offset)
    
    return f"{base_url}?{urlencode(params)}"


async def fetch_page_with_playwright(browser, category: Dict[str, Any], page_num: int, page_offset: int, debug_folder: Path, max_retries: int = 10) -> Dict[str, Any]:
    """
    Fetch a single page for a category using Playwright with exponential backoff for rate limiting.
    Returns the parsed JSON data or raises an exception.
    """
    category_name = category["category_name"]
    target_url = get_category_url(category, page_offset)
    
    base_backoff_seconds = 5.0
    
    for attempt in range(max_retries):
        page = None
        try:
            page = await browser.new_page()
            
            if attempt > 0:
                print(f"  🔄 Retrying page {page_num} ({attempt + 1}/{max_retries}) for {category_name}...")
                
            await page.goto(target_url, wait_until="networkidle", timeout=60000)
            
            html_content = await page.content()
            
            # Debug: Save raw HTML
            category_safe_name = sanitize_filename(category_name)
            debug_html_file = debug_folder / f"{category_safe_name}_page_{page_num}_attempt_{attempt + 1}.html"
            with open(debug_html_file, 'w', encoding='utf-8') as f:
                f.write(html_content)
            print(f"  🐛 Debug: Saved HTML to {debug_html_file}")
            
            soup = BeautifulSoup(html_content, 'html.parser')
            
            initial_state_script = soup.find('script', string=re.compile(r'window\.___INITIAL_STATE___'))
            
            if initial_state_script:
                script_content = initial_state_script.string
                match = re.search(r'window\.___INITIAL_STATE___\s*=\s*(\{.*?\});', script_content, re.DOTALL)
                
                if match:
                    json_text = match.group(1)
                    
                    # Debug: Save raw JSON text
                    debug_json_raw_file = debug_folder / f"{category_safe_name}_page_{page_num}_attempt_{attempt + 1}_raw.json"
                    with open(debug_json_raw_file, 'w', encoding='utf-8') as f:
                        f.write(json_text)
                    print(f"  🐛 Debug: Saved raw JSON to {debug_json_raw_file}")
                    
                    try:
                        json_data = json.loads(json_text)
                        
                        # Debug: Save parsed JSON
                        debug_json_parsed_file = debug_folder / f"{category_safe_name}_page_{page_num}_attempt_{attempt + 1}_parsed.json"
                        with open(debug_json_parsed_file, 'w', encoding='utf-8') as f:
                            json.dump(json_data, f, indent=2)
                        print(f"  🐛 Debug: Saved parsed JSON to {debug_json_parsed_file}")
                        
                        # Check if we have valid category data (not rate limited)
                        category_data = json_data.get("instamart", {}).get("categoryData", {})
                        
                        # Debug: Log what we found
                        print(f"  🐛 Debug: instamart exists: {'instamart' in json_data}")
                        print(f"  🐛 Debug: categoryData exists: {'categoryData' in json_data.get('instamart', {})}")
                        if category_data:
                            print(f"  🐛 Debug: categoryData keys: {list(category_data.keys())}")
                            print(f"  🐛 Debug: categories count: {len(category_data.get('categories', []))}")
                            print(f"  🐛 Debug: filters count: {len(category_data.get('filters', []))}")
                            print(f"  🐛 Debug: widgets count: {len(category_data.get('widgets', []))}")
                            print(f"  🐛 Debug: hasMore: {category_data.get('hasMore', 'not found')}")
                            print(f"  🐛 Debug: offset: {category_data.get('offset', 'not found')}")
                            
                            # Debug widget types
                            widgets = category_data.get('widgets', [])
                            for i, widget in enumerate(widgets):
                                widget_info = widget.get("widgetInfo", {})
                                widget_type = widget_info.get("widgetType", "unknown")
                                widget_data = widget.get("data")
                                data_count = len(widget_data) if widget_data is not None else 0
                                print(f"  🐛 Debug: Widget {i}: type={widget_type}, data_count={data_count}")
                            
                            # Test product counting (inline to avoid circular dependency)
                            test_widgets = category_data.get("widgets", [])
                            test_product_count = 0
                            for test_widget in test_widgets:
                                test_widget_info = test_widget.get("widgetInfo", {})
                                if test_widget_info.get("widgetType") == "PRODUCT_LIST":
                                    test_products = test_widget.get("data")
                                    if test_products is not None:
                                        test_product_count += len(test_products)
                            print(f"  🐛 Debug: Total products found: {test_product_count}")
                        
                        if category_data and (category_data.get("categories") or category_data.get("filters") or category_data.get("widgets")):
                            return json_data
                        else:
                            print(f"  ⚠️ Rate limited on attempt {attempt + 1} (empty categoryData) for {category_name}, page {page_num}.")
                    except json.JSONDecodeError as e:
                        print(f"  ⚠️ JSON decode error on attempt {attempt + 1}: {e}")
                else:
                    print(f"  ⚠️ No JSON match on attempt {attempt + 1} for {category_name}, page {page_num}.")
            else:
                print(f"  ⚠️ No ___INITIAL_STATE___ script found on attempt {attempt + 1} for {category_name}, page {page_num}.")
                
        except PlaywrightTimeoutError:
            print(f"  ⚠️ Timeout on attempt {attempt + 1} for {category_name}, page {page_num}.")
        except Exception as e:
            print(f"  ⚠️ Error on attempt {attempt + 1} for {category_name}, page {page_num}: {e}")
        
        finally:
            if page:
                await page.close()

        # If we got here, it's a failure for this attempt. Wait before the next one.
        if attempt < max_retries - 1:
            delay = base_backoff_seconds * (2 ** attempt)
            print(f"  ⏳ Backing off for {delay:.1f}s...")
            await asyncio.sleep(delay)
    
    raise Exception(f"Max retries ({max_retries}) reached for {category_name}, page {page_num}")


def extract_discovered_categories(response_data: Dict[str, Any], source_category: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract newly discovered related categories and filters from response"""
    discovered = []
    
    # For stored Playwright data, we look in raw_response.data (which contains categoryData contents)
    data = response_data.get("raw_response", {}).get("data", {})
    if not data:
        return discovered
    
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


def get_existing_pages(categories_folder: Path, category_name: str) -> List[int]:
    """Get list of existing page numbers for a category"""
    category_safe_name = sanitize_filename(category_name)
    pattern = f"{category_safe_name}_page_*.json"
    
    existing_pages = []
    for file_path in categories_folder.glob(pattern):
        try:
            # Extract page number from filename
            page_match = re.search(r'_page_(\d+)\.json$', file_path.name)
            if page_match:
                page_num = int(page_match.group(1))
                existing_pages.append(page_num)
        except (ValueError, AttributeError):
            continue
    
    return sorted(existing_pages)


def get_next_page_to_scrape(categories_folder: Path, category_name: str) -> int:
    """Determine the next page number to scrape for resumable operation"""
    existing_pages = get_existing_pages(categories_folder, category_name)
    
    if not existing_pages:
        return 0  # Start from page 0
    
    # Check if the last page has hasMore=False (category complete)
    last_page = max(existing_pages)
    category_name_safe = sanitize_filename(category_name)
    last_page_file = categories_folder / f"{category_name_safe}_page_{last_page}.json"
    
    try:
        if last_page_file.exists():
            with open(last_page_file, 'r') as f:
                data = json.load(f)
                has_more = data.get("metadata", {}).get("has_more", True)
                
                if not has_more:
                    print(f"    📋 Category {category_name} is complete (hasMore=False on page {last_page})")
                    return -1  # Special value indicating category is complete
    except Exception as e:
        print(f"    ⚠️  Warning: Could not check completion status: {e}")
    
    # Find the first missing page number
    for i, page_no in enumerate(existing_pages):
        if page_no != i:
            return i  # Found a gap
    
    # No gaps found, continue from the next page
    return len(existing_pages)


def is_category_started(categories_folder: Path, category_name: str) -> bool:
    """Check if a category has any pages scraped"""
    existing_pages = get_existing_pages(categories_folder, category_name)
    return len(existing_pages) > 0


def count_products_in_playwright_response(response_data: Dict[str, Any]) -> int:
    """Count products in a Playwright category listing response"""
    # For stored data, look in raw_response.data; for live data, look in instamart.categoryData
    if "raw_response" in response_data:
        # Stored format: raw_response.data contains categoryData contents
        data = response_data.get("raw_response", {}).get("data", {})
    else:
        # Live format: instamart.categoryData
        data = response_data.get("instamart", {}).get("categoryData", {})
    
    widgets = data.get("widgets", [])
    
    total_products = 0
    for widget in widgets:
        # Look for PRODUCT_LIST widgets in the new structure
        widget_info = widget.get("widgetInfo", {})
        if widget_info.get("widgetType") == "PRODUCT_LIST":
            # Products are in the "data" array of the widget (can be None)
            products = widget.get("data")
            if products is not None:
                total_products += len(products)
        
        # Also check for old GridWidget structure for compatibility
        elif widget.get("@type") == "type.googleapis.com/swiggy.gandalf.widgets.v2.GridWidget":
            grid_elements = widget.get("gridElements", {})
            info_list = grid_elements.get("infoWithStyle", {}).get("info", [])
            total_products += len(info_list)
    
    return total_products


def count_products_in_existing_pages(categories_folder: Path, category_name: str, existing_pages: List[int]) -> int:
    """Count products from existing pages"""
    total_products = 0
    category_safe_name = sanitize_filename(category_name)
    
    for page_num in existing_pages:
        try:
            page_file = categories_folder / f"{category_safe_name}_page_{page_num}.json"
            if page_file.exists():
                with open(page_file, 'r') as f:
                    page_data = json.load(f)
                    response_data = page_data.get("raw_response", {})
                    products = count_products_in_playwright_response(response_data)
                    total_products += products
        except Exception:
            pass  # Skip if can't read existing file
    
    return total_products


async def scrape_category_with_pagination_playwright(
    browser, 
    config: Dict[str, Any], 
    category: Dict[str, Any], 
    categories_folder: Path, 
    errors_folder: Path, 
    debug_folder: Path,
    resume: bool = True
) -> Tuple[int, int]:
    """
    Scrape all pages for a category using Playwright with pagination support.
    Returns (pages_scraped, total_products).
    """
    category_name = category["category_name"]
    category_safe_name = sanitize_filename(category_name)
    
    # Determine starting page for resumable operation
    if resume:
        start_page = get_next_page_to_scrape(categories_folder, category_name)
        existing_pages = get_existing_pages(categories_folder, category_name)
        
        # Check if category is already complete
        if start_page == -1:
            print(f"  ✅ Category {category_name} already complete, skipping")
            pages_scraped = len(existing_pages)
            total_products = count_products_in_existing_pages(categories_folder, category_name, existing_pages)
            return pages_scraped, total_products
        
        if existing_pages and start_page > 0:
            print(f"  🔄 Resuming from page {start_page} (found existing pages: {existing_pages})")
        else:
            print(f"  🆕 Starting fresh scrape from page 0")
    else:
        start_page = 0
        existing_pages = []
    
    # Count existing pages and products
    pages_scraped = len(existing_pages)
    total_products = count_products_in_existing_pages(categories_folder, category_name, existing_pages)
    
    page_num = start_page
    current_offset = 0  # Will be updated from API response
    
    # If resuming, get the offset from the last existing page
    if existing_pages and start_page > 0:
        try:
            last_page = max(existing_pages)
            category_safe_name = sanitize_filename(category_name)
            last_page_file = categories_folder / f"{category_safe_name}_page_{last_page}.json"
            if last_page_file.exists():
                with open(last_page_file, 'r') as f:
                    last_page_data = json.load(f)
                    current_offset = last_page_data.get("metadata", {}).get("next_offset", 0)
                    print(f"  🔄 Resuming with offset {current_offset} from last page {last_page}")
        except Exception as e:
            print(f"  ⚠️ Could not get offset from last page, starting from 0: {e}")
            current_offset = 0
    
    while True:
        try:
            print(f"  📄 Fetching page {page_num} (offset: {current_offset})...")
            
            # Fetch the page using Playwright
            response_data = await fetch_page_with_playwright(browser, category, page_num, current_offset, debug_folder)
            
            # Extract category data (Playwright structure)
            category_data = response_data.get("instamart", {}).get("categoryData", {})
            
            # Check pagination info (same as original API)
            has_more = category_data.get("hasMore", False)
            next_offset = category_data.get("offset", current_offset)
            
            # Count products in this page (using same logic as original)
            page_products = count_products_in_playwright_response(response_data)
            
            print(f"    ✓ Page {page_num}: {page_products} products, hasMore: {has_more}")
            
            # Check if we have products
            if page_products == 0:
                print(f"  ℹ️ No products found on page {page_num}, ending pagination")
                break
            
            # Create page metadata (matching original format)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            page_data = {
                "metadata": {
                    "category_id": category["id"],
                    "category_name": category["category_name"],
                    "page_no": page_num,
                    "offset": current_offset,
                    "next_offset": next_offset,
                    "has_more": has_more,
                    "timestamp": timestamp,
                    "scraped_at": datetime.now().isoformat(),
                    "method": "playwright"
                },
                "raw_response": {
                    "data": category_data  # Store only the categoryData contents as "data" to match original structure
                }
            }
            
            # Save page to file
            page_filename = f"{category_safe_name}_page_{page_num}.json"
            page_file_path = categories_folder / page_filename
            
            with open(page_file_path, 'w') as f:
                json.dump(page_data, f, indent=2)
            
            pages_scraped += 1
            total_products += page_products
            
            print(f"  ✅ Page {page_num}: {page_products} products saved to {page_filename}")
            
            # Check if we should continue (same logic as original)
            if not has_more:
                print(f"    🏁 Finished scraping {category_name} - no more pages")
                break
            
            # Setup for next page (same as original)
            page_num += 1
            current_offset = next_offset
            
        except Exception as e:
            print(f"  ❌ Error fetching page {page_num}: {e}")
            
            # Save error details
            error_data = {
                "error": str(e),
                "category_id": category["id"],
                "category_name": category["category_name"],
                "page_no": page_num,
                "offset": current_offset,
                "timestamp": datetime.now().isoformat()
            }
            
            error_filename = f"ERROR_{category_safe_name}_page_{page_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            error_file_path = errors_folder / error_filename
            
            with open(error_file_path, 'w') as f:
                json.dump(error_data, f, indent=2)
            
            break
    
    return pages_scraped, total_products


async def process_single_category(
    browser, 
    config: Dict[str, Any], 
    category: Dict[str, Any], 
    categories_folder: Path, 
    discovered_folder: Path, 
    errors_folder: Path,
    debug_folder: Path,
    category_index: int,
    total_categories: int
) -> Dict[str, Any]:
    """Process a single category and return results"""
    category_name = category["category_name"]
    
    print(f"\n📦 Processing category {category_index}/{total_categories}: {category_name}")
    print(f"   Group: {category['category_group']}")
    
    # Check if category has been started
    if is_category_started(categories_folder, category_name):
        existing_pages = get_existing_pages(categories_folder, category_name)
        print(f"  🔄 Resuming category (found existing pages: {existing_pages})")
    
    try:
        # Scrape all pages for this category
        pages, products = await scrape_category_with_pagination_playwright(
            browser, config, category, categories_folder, errors_folder, debug_folder, resume=True
        )
        
        result = {
            "category_name": category_name,
            "status": "success" if pages > 0 else "failed",
            "pages": pages,
            "products": products,
            "discovered": 0
        }
        
        if pages > 0:
            # For the first page, extract discovered categories
            try:
                category_safe_name = sanitize_filename(category_name)
                first_page_file = categories_folder / f"{category_safe_name}_page_0.json"
                
                if first_page_file.exists():
                    with open(first_page_file, 'r') as f:
                        page_data = json.load(f)
                        response_data = page_data.get("raw_response", {})
                        
                        # Extract discovered categories from first page
                        discovered_items = extract_discovered_categories(response_data, category)
                        if discovered_items:
                            save_discovered_categories(discovered_folder, category, discovered_items)
                            result["discovered"] = len(discovered_items)
            except Exception as e:
                print(f"  ⚠️  Warning: Could not extract discovered categories: {e}")
            
            print(f"  ✅ Successfully scraped {pages} pages with {products} products")
        else:
            print(f"  ❌ Failed to scrape any pages")
            
        return result
        
    except Exception as e:
        print(f"  ❌ Failed to process {category_name}: {e}")
        return {
            "category_name": category_name,
            "status": "failed",
            "pages": 0,
            "products": 0,
            "discovered": 0,
            "error": str(e)
        }


async def process_categories_in_parallel(
    categories: List[Dict[str, Any]], 
    config: Dict[str, Any], 
    categories_folder: Path, 
    discovered_folder: Path, 
    errors_folder: Path,
    debug_folder: Path,
    max_concurrent: int = 20
):
    """Process categories in parallel batches"""
    total_categories = len(categories)
    all_results = []
    
    # Split categories into chunks
    chunk_size = max_concurrent
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        try:
            for i in range(0, total_categories, chunk_size):
                chunk = categories[i:i + chunk_size]
                chunk_num = i // chunk_size + 1
                total_chunks = (total_categories + chunk_size - 1) // chunk_size
                
                print(f"\n{'='*60}")
                print(f"🚀 Processing Batch {chunk_num}/{total_chunks} ({len(chunk)} categories)")
                print(f"{'='*60}")
                
                # Create tasks for this batch
                tasks = [
                    process_single_category(
                        browser, config, category, categories_folder, 
                        discovered_folder, errors_folder, debug_folder,
                        i + j + 1, total_categories
                    )
                    for j, category in enumerate(chunk)
                ]
                
                # Run batch concurrently
                batch_results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Process results
                for result in batch_results:
                    if isinstance(result, Exception):
                        print(f"  ❌ Exception: {result}")
                        all_results.append({
                            "category_name": "unknown",
                            "status": "exception",
                            "pages": 0,
                            "products": 0,
                            "discovered": 0,
                            "error": str(result)
                        })
                    else:
                        all_results.append(result)
                
                print(f"\n✅ Completed Batch {chunk_num}/{total_chunks}")
                
                # Small delay between batches
                if i + chunk_size < total_categories:
                    print(f"⏳ Waiting 5s before next batch...")
                    await asyncio.sleep(5)
                    
        finally:
            await browser.close()
    
    return all_results


async def main():
    """Main function"""
    print("🚀 Starting Step 2 (Playwright): Get Category Listings from Swiggy (with Pagination)")
    print("=" * 80)
    
    try:
        # Load config and categories
        config = load_config()
        print("✓ Loaded configuration")
        
        categories = load_categories(config)
        print(f"✓ Loaded {len(categories)} categories from step1")
        
        # Filter out categories with age consent (as done in test script)
        filtered_categories = []
        skipped_categories = []
        
        for category in categories:
            if "ageConsent" in category.get("deeplink", ""):
                skipped_categories.append(category["category_name"])
            else:
                filtered_categories.append(category)
        
        if skipped_categories:
            print(f"⚠️ Skipping {len(skipped_categories)} categories with age consent: {', '.join(skipped_categories[:5])}{'...' if len(skipped_categories) > 5 else ''}")
        
        categories = filtered_categories
        print(f"✓ Processing {len(categories)} categories (after filtering age consent)")
        
        if not categories:
            print("❌ No categories to process after filtering.")
            return
        
        # Setup folders
        categories_folder, categories_all_folder, discovered_folder, errors_folder, debug_folder = setup_step2_folders(config)
        
        # Get parallel processing settings
        max_concurrent = config.get("max_concurrent_categories", 20)
        print(f"⚡ Using {max_concurrent} concurrent workers")
        
        # Process categories in parallel
        all_results = await process_categories_in_parallel(
            categories, config, categories_folder, discovered_folder, errors_folder, debug_folder, max_concurrent
        )
        
        # Analyze results
        successful_categories = sum(1 for r in all_results if r["status"] == "success")
        failed_categories = sum(1 for r in all_results if r["status"] != "success")
        total_pages_scraped = sum(r["pages"] for r in all_results)
        total_products_scraped = sum(r["products"] for r in all_results)
        total_discovered = sum(r["discovered"] for r in all_results)
        
        # Final summary
        print("\n" + "=" * 80)
        print("📊 FINAL SUMMARY:")
        print(f"   Total categories: {len(categories)}")
        print(f"   ✅ Successful categories: {successful_categories}")
        print(f"   ❌ Failed categories: {failed_categories}")
        print(f"   📄 Total pages scraped: {total_pages_scraped}")
        print(f"   🛍️  Total products scraped: {total_products_scraped}")
        print(f"   🔍 Total related categories/filters discovered: {total_discovered}")
        print(f"   📁 Pages saved in: {categories_folder}")
        print(f"   🔍 Discovered categories in: {discovered_folder}")
        print(f"   ❌ Errors saved in: {errors_folder}")
        
        if successful_categories > 0:
            print("\n✅ Step 2 (Playwright) completed!")
            print(f"🎉 Successfully scraped {total_products_scraped} products from {successful_categories} categories!")
            if total_discovered > 0:
                print(f"🔍 Bonus: Discovered {total_discovered} related categories and filters for Step 3!")
        else:
            print("\n❌ Step 2 (Playwright) failed - no successful category scrapes")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())