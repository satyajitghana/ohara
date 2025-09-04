#!/usr/bin/env python3
"""
Step 3 (Playwright): Scrape products from discovered categories with pagination support
This script reads the output JSON files from step2 playwright version and extracts discovered categories,
then scrapes all products with pagination using Playwright.
Fully resumable - can be stopped and restarted to continue where it left off.
"""

import asyncio
import json
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Set
from urllib.parse import urlencode, unquote
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

# Import from utils
from utils.common import (
    load_config, sanitize_filename, setup_base_folders
)


def load_discovered_categories_from_playwright_output(config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Load discovered categories from step2 playwright output JSON files"""
    responses_folder = Path(config["responses_folder"])
    categories_folder = responses_folder / "raw" / "categories"
    
    all_discovered = []
    seen_categories = set()  # Track by ID to avoid duplicates
    
    # Find all category page JSON files
    category_files = list(categories_folder.glob("*_page_*.json"))
    print(f"Found {len(category_files)} category page files to analyze")
    
    for file_path in category_files:
        try:
            with open(file_path, 'r') as f:
                data = json.load(f)
                
            # Extract source category info from metadata
            metadata = data.get("metadata", {})
            source_category = {
                "id": metadata.get("category_id", ""),
                "category_name": metadata.get("category_name", ""),
                "category_group": "unknown"  # Not stored in playwright metadata
            }
            
            # Extract discovered categories from raw_response
            response_data = data.get("raw_response", {})
            discovered_items = extract_discovered_categories_from_response(response_data, source_category)
            
            # Add unique discovered categories
            for item in discovered_items:
                if item["type"] == "related_category":
                    category_id = item["id"]
                    if category_id not in seen_categories:
                        seen_categories.add(category_id)
                        all_discovered.append(item)
                        
        except Exception as e:
            print(f"Error reading {file_path}: {e}")
    
    print(f"✓ Found {len(all_discovered)} unique discovered categories")
    return all_discovered


def extract_discovered_categories_from_response(response_data: Dict[str, Any], source_category: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract discovered categories and filters from Playwright response"""
    discovered = []
    
    # The response_data passed in is the content of "raw_response" from the stored file
    data = response_data.get("data", {})
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


def setup_step3_folders(config: Dict[str, Any]):
    """Create Step 3 specific folders"""
    responses_folder, categories_folder, categories_all_folder, discovered_folder, errors_folder = setup_base_folders(config)
    
    # Create debug folder for step3
    debug_folder = Path(config["responses_folder"]) / "debug"
    debug_folder.mkdir(exist_ok=True)
    
    print(f"✓ Created folder structure:")
    print(f"   Categories (Step 2 input): {categories_folder}")
    print(f"   Categories-All (Output): {categories_all_folder}")
    print(f"   Discovered (raw): {discovered_folder}")
    print(f"   Errors: {errors_folder}")
    print(f"   Debug: {debug_folder}")
    
    return categories_folder, categories_all_folder, discovered_folder, errors_folder, debug_folder


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


def is_category_fully_scraped(categories_folder: Path, category_name: str) -> bool:
    """Check if a category has been fully scraped (hasMore=False on last page)"""
    existing_pages = get_existing_pages(categories_folder, category_name)
    
    if not existing_pages:
        return False
    
    # Check if the last page has hasMore=False
    last_page = max(existing_pages)
    category_name_safe = sanitize_filename(category_name)
    last_page_file = categories_folder / f"{category_name_safe}_page_{last_page}.json"
    
    try:
        if last_page_file.exists():
            with open(last_page_file, 'r') as f:
                data = json.load(f)
                has_more = data.get("metadata", {}).get("has_more", True)
                return not has_more  # Category is complete if hasMore=False
    except Exception:
        pass
    
    # If we can't determine, assume not complete
    return False


def copy_categories_to_all_folder(categories_folder: Path, categories_all_folder: Path) -> int:
    """Copy all category files from categories to categories-all folder"""
    copied_count = 0
    
    for category_file in categories_folder.glob("*.json"):
        dest_file = categories_all_folder / category_file.name
        
        if not dest_file.exists():
            try:
                with open(category_file, 'r') as f:
                    data = json.load(f)
                
                with open(dest_file, 'w') as f:
                    json.dump(data, f, indent=2)
                
                copied_count += 1
                print(f"  📋 Copied {category_file.name}")
                
            except Exception as e:
                print(f"  ❌ Error copying {category_file.name}: {e}")
    
    print(f"✓ Copied {copied_count} category files to categories-all folder")
    return copied_count


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
        
        # Create a category object similar to step1 format but without deeplink
        # We'll need to construct the URL from the category ID
        unique_categories.append({
            "id": category_id,
            "category_name": category_name,
            "productCount": item.get("productCount", 0),
            "imageId": item.get("imageId", ""),
            "ageConsentRequired": item.get("ageConsentRequired", False),
            "category_group": "Discovered"  # Mark as discovered
        })
    
    return unique_categories


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


def get_category_url_by_id(category_id: str, page_offset: int = 0) -> str:
    """Generate category URL using category ID (since we don't have deeplink for discovered categories)"""
    base_url = "https://www.swiggy.com/instamart/category-listing"
    
    # Build params for discovered category
    params = {
        "categoryId": category_id,
        "custom_back": "true"
    }
    
    # Always set the offset to handle pagination correctly
    params["offset"] = str(page_offset)
    
    return f"{base_url}?{urlencode(params)}"


async def fetch_page_with_playwright(browser, category: Dict[str, Any], page_num: int, page_offset: int, debug_folder: Path, max_retries: int = 10) -> Dict[str, Any]:
    """
    Fetch a single page for a discovered category using Playwright with exponential backoff for rate limiting.
    Returns the parsed JSON data or raises an exception.
    """
    category_name = category["category_name"]
    target_url = get_category_url_by_id(category["id"], page_offset)
    
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
            debug_html_file = debug_folder / f"step3_{category_safe_name}_page_{page_num}_attempt_{attempt + 1}.html"
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
                    debug_json_raw_file = debug_folder / f"step3_{category_safe_name}_page_{page_num}_attempt_{attempt + 1}_raw.json"
                    with open(debug_json_raw_file, 'w', encoding='utf-8') as f:
                        f.write(json_text)
                    print(f"  🐛 Debug: Saved raw JSON to {debug_json_raw_file}")
                    
                    try:
                        json_data = json.loads(json_text)
                        
                        # Debug: Save parsed JSON
                        debug_json_parsed_file = debug_folder / f"step3_{category_safe_name}_page_{page_num}_attempt_{attempt + 1}_parsed.json"
                        with open(debug_json_parsed_file, 'w', encoding='utf-8') as f:
                            json.dump(json_data, f, indent=2)
                        print(f"  🐛 Debug: Saved parsed JSON to {debug_json_parsed_file}")
                        
                        # Check if we have valid category data (not rate limited)
                        category_data = json_data.get("instamart", {}).get("categoryData", {})
                        
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


async def scrape_discovered_category_with_pagination_playwright(
    browser,
    config: Dict[str, Any],
    category: Dict[str, Any],
    categories_all_folder: Path,
    errors_folder: Path,
    debug_folder: Path,
    resume: bool = True
) -> tuple[int, int]:
    """
    Scrape all pages for a discovered category using Playwright with pagination support.
    Returns (pages_scraped, total_products).
    """
    category_name = category["category_name"]
    category_safe_name = sanitize_filename(category_name)
    
    # Determine starting page for resumable operation
    if resume:
        start_page = get_next_page_to_scrape(categories_all_folder, category_name)
        existing_pages = get_existing_pages(categories_all_folder, category_name)
        
        # Check if category is already complete
        if start_page == -1:
            print(f"  ✅ Category {category_name} already complete, skipping")
            pages_scraped = len(existing_pages)
            total_products = count_products_in_existing_pages(categories_all_folder, category_name, existing_pages)
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
    total_products = count_products_in_existing_pages(categories_all_folder, category_name, existing_pages)
    
    page_num = start_page
    current_offset = 0  # Will be updated from API response
    
    # If resuming, get the offset from the last existing page
    if existing_pages and start_page > 0:
        try:
            last_page = max(existing_pages)
            category_safe_name = sanitize_filename(category_name)
            last_page_file = categories_all_folder / f"{category_safe_name}_page_{last_page}.json"
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
                    "method": "playwright",
                    "source": "step3_discovered"
                },
                "raw_response": {
                    "data": category_data  # Store only the categoryData contents as "data" to match original structure
                }
            }
            
            # Save page to file
            page_filename = f"{category_safe_name}_page_{page_num}.json"
            page_file_path = categories_all_folder / page_filename
            
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
                "timestamp": datetime.now().isoformat(),
                "source": "step3_discovered"
            }
            
            error_filename = f"ERROR_step3_{category_safe_name}_page_{page_num}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            error_file_path = errors_folder / error_filename
            
            with open(error_file_path, 'w') as f:
                json.dump(error_data, f, indent=2)
            
            break
    
    return pages_scraped, total_products


async def process_single_discovered_category(
    browser,
    config: Dict[str, Any],
    category: Dict[str, Any],
    categories_all_folder: Path,
    errors_folder: Path,
    debug_folder: Path,
    category_index: int,
    total_categories: int
) -> Dict[str, Any]:
    """Process a single discovered category and return results"""
    category_name = category["category_name"]
    
    print(f"\n📦 Processing discovered category {category_index}/{total_categories}: {category_name}")
    print(f"   Expected products: {category['productCount']}")
    
    try:
        # Scrape all pages for this discovered category
        pages, products = await scrape_discovered_category_with_pagination_playwright(
            browser, config, category, categories_all_folder, errors_folder, debug_folder, resume=True
        )
        
        result = {
            "category_name": category_name,
            "status": "success" if pages > 0 else "failed",
            "pages": pages,
            "products": products
        }
        
        if pages > 0:
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
            "error": str(e)
        }


async def process_discovered_categories_in_parallel(
    discovered_categories: List[Dict[str, Any]],
    config: Dict[str, Any],
    categories_all_folder: Path,
    errors_folder: Path,
    debug_folder: Path,
    max_concurrent: int = 20
):
    """Process discovered categories in parallel batches"""
    total_categories = len(discovered_categories)
    all_results = []
    
    # Split categories into chunks
    chunk_size = max_concurrent
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        try:
            for i in range(0, total_categories, chunk_size):
                chunk = discovered_categories[i:i + chunk_size]
                chunk_num = i // chunk_size + 1
                total_chunks = (total_categories + chunk_size - 1) // chunk_size
                
                print(f"\n{'='*60}")
                print(f"🚀 Processing Batch {chunk_num}/{total_chunks} ({len(chunk)} discovered categories)")
                print(f"{'='*60}")
                
                # Create tasks for this batch
                tasks = [
                    process_single_discovered_category(
                        browser, config, category, categories_all_folder,
                        errors_folder, debug_folder,
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
    print("🚀 Starting Step 3 (Playwright): Scrape Discovered Categories with Pagination")
    print("=" * 80)
    
    try:
        # Load config
        config = load_config()
        print("✓ Loaded configuration")
        
        # Load discovered categories from step2 playwright output
        discovered_items = load_discovered_categories_from_playwright_output(config)
        print(f"✓ Loaded {len(discovered_items)} discovered items from step2 playwright output")
        
        # Setup folders
        categories_folder, categories_all_folder, discovered_folder, errors_folder, debug_folder = setup_step3_folders(config)
        
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
        
        # Get parallel processing settings
        max_concurrent = config.get("max_concurrent_categories", 20)
        print(f"⚡ Using {max_concurrent} concurrent workers")
        
        # Process discovered categories in parallel
        all_results = await process_discovered_categories_in_parallel(
            unique_categories, config, categories_all_folder, errors_folder, debug_folder, max_concurrent
        )
        
        # Analyze results
        successful_categories = sum(1 for r in all_results if r["status"] == "success")
        failed_categories = sum(1 for r in all_results if r["status"] != "success")
        total_pages_scraped = sum(r["pages"] for r in all_results)
        total_products_scraped = sum(r["products"] for r in all_results)
        
        # Final summary
        print("\n" + "=" * 80)
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
            print("\n✅ Step 3 (Playwright) completed!")
            print(f"🎉 Successfully scraped {total_products_scraped} products from {successful_categories} discovered categories!")
        else:
            print("\n✅ Step 3 (Playwright) completed - no new categories to scrape!")
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    asyncio.run(main())
