#!/usr/bin/env python3
"""
Common utilities for Swiggy scraping
"""

import json
import requests
import time
import re
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Tuple
from urllib.parse import urlparse, parse_qs


def load_config() -> Dict[str, Any]:
    """Load configuration from config-v2.json"""
    config_path = Path("config-v2.json")
    if not config_path.exists():
        raise FileNotFoundError("config-v2.json not found. Please create it in the project root.")
    
    with open(config_path, 'r') as f:
        return json.load(f)


def sanitize_filename(filename: str) -> str:
    """Sanitize filename to be filesystem-safe"""
    filename = re.sub(r'[<>:"/\\|?*]', '_', filename)
    filename = re.sub(r'\s+', '_', filename)
    filename = re.sub(r'_+', '_', filename)
    return filename.strip('_')


def exponential_backoff(attempt: int, base_delay: float = 15.0, max_delay: float = 120.0) -> float:
    """Calculate exponential backoff delay"""
    delay = min(base_delay * (2 ** attempt), max_delay)
    print(f"  ⏳ Rate limited! Backing off for {delay:.1f}s (attempt {attempt + 1})")
    return delay


def is_rate_limited(status_code: int, error_msg: str) -> bool:
    """Check if the response indicates rate limiting"""
    rate_limit_indicators = [
        status_code == 202,  # Swiggy returns 202 for rate limits
        status_code == 429,  # Standard rate limit status
        status_code == 503,  # Service unavailable 
        "Non-200 status code: 202" in error_msg,  # Our specific 202 error
        "JSON decode error" in error_msg,  # Empty response often means rate limited
        "rate limit" in error_msg.lower(),
        "too many requests" in error_msg.lower()
    ]
    return any(rate_limit_indicators)


def parse_deeplink_params(deeplink: str) -> Dict[str, str]:
    """Extract parameters from Swiggy deeplink URL"""
    params = {}
    
    # Handle both regular URLs and Swiggy deeplinks
    if deeplink.startswith("swiggy://"):
        # Extract the URL part after swiggy://
        if "?" in deeplink:
            query_part = deeplink.split("?", 1)[1]
            # Parse the query string
            for param_pair in query_part.split("&"):
                if "=" in param_pair:
                    key, value = param_pair.split("=", 1)
                    params[key] = value
    elif deeplink.startswith("swiggy://ageConsent"):
        # Handle age consent URLs - extract the embedded URL
        if "url=" in deeplink:
            encoded_url = deeplink.split("url=", 1)[1]
            # URL decode the embedded URL
            import urllib.parse
            decoded_url = urllib.parse.unquote(encoded_url)
            return parse_deeplink_params(decoded_url)
    
    return params


def make_category_listing_request(config: Dict[str, Any], category: Dict[str, Any], page_no: int = 0, offset: int = 0) -> Tuple[Dict[str, Any], int, str]:
    """Make request to category listing API with pagination"""
    base_url = config["base_url"]
    endpoint = config["api_endpoints"]["category_listing"]
    headers = config["headers"]
    cookies_str = config["cookies"]
    
    # Build API parameters for category listing
    api_params = {
        "categoryName": category["category_name"],
        "storeId": config["default_params"]["storeId"],
        "offset": str(offset),
        "pageNo": str(page_no),
        "filterName": "",
        "primaryStoreId": config["default_params"]["primaryStoreId"],
        "secondaryStoreId": config["default_params"]["secondaryStoreId"],
        "taxonomyType": "Speciality taxonomy 1"  # Default taxonomy type
    }
    
    # If we have deeplink params, use those for taxonomy type
    if "deeplink" in category:
        deeplink_params = parse_deeplink_params(category["deeplink"])
        if "taxonomyType" in deeplink_params:
            api_params["taxonomyType"] = deeplink_params["taxonomyType"]
    
    # Convert cookies string to dict
    cookies = {}
    for cookie in cookies_str.split('; '):
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            cookies[key] = value
    
    url = f"{base_url}{endpoint}"
    
    print(f"  Making request for: {category['category_name']} (page {page_no}, offset {offset})")
    
    try:
        response = requests.get(
            url,
            headers=headers,
            cookies=cookies,
            params=api_params,
            timeout=30
        )
        
        print(f"  ✓ HTTP Response Status: {response.status_code}")
        
        # Only 200 is success for Swiggy API
        if response.status_code != 200:
            error_msg = f"Non-200 status code: {response.status_code}"
            print(f"  ✗ {error_msg}")
            return {"error": error_msg, "status_code": response.status_code, "response_text": response.text[:500]}, response.status_code, error_msg
        
        try:
            json_data = response.json()
            print(f"  ✓ JSON parsed successfully")
            return json_data, response.status_code, ""
        except (json.JSONDecodeError, ValueError) as e:
            error_msg = f"JSON decode error: {str(e)}"
            print(f"  ✗ {error_msg}")
            return {"error": error_msg, "status_code": response.status_code, "response_text": response.text[:500]}, response.status_code, error_msg
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Request failed: {str(e)}"
        print(f"  ✗ {error_msg}")
        return {"error": error_msg}, 0, error_msg


def save_category_page_response(output_folder: Path, category: Dict[str, Any], response_data: Dict[str, Any], page_no: int, offset: int, status_code: int):
    """Save category page response with pagination info"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Create filename with pagination info
    category_name = sanitize_filename(category["category_name"])
    filename = f"{category_name}_page_{page_no}.json"
    
    response_file = output_folder / filename
    
    # Extract pagination info from response
    data = response_data.get("data", {})
    has_more = data.get("hasMore", False)
    next_offset = data.get("offset", offset)
    
    # Add metadata to the response
    enriched_response = {
        "metadata": {
            "category_id": category.get("id", ""),
            "category_name": category["category_name"],
            "page_no": page_no,
            "offset": offset,
            "next_offset": next_offset,
            "has_more": has_more,
            "timestamp": timestamp,
            "scraped_at": datetime.now().isoformat(),
            "status_code": status_code
        },
        "raw_response": response_data
    }
    
    with open(response_file, 'w') as f:
        json.dump(enriched_response, f, indent=2)
    
    print(f"  ✓ Saved to: {response_file}")
    return response_file


def save_error_response(errors_folder: Path, category: Dict[str, Any], error_data: Dict[str, Any], page_no: int, offset: int, status_code: int, error_msg: str):
    """Save error response with pagination info"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    category_name = sanitize_filename(category["category_name"])
    filename = f"ERROR_{category_name}_page{page_no}_offset{offset}_{timestamp}.json"
    
    error_file = errors_folder / filename
    
    enriched_error = {
        "metadata": {
            "category_id": category.get("id", ""),
            "category_name": category["category_name"],
            "page_no": page_no,
            "offset": offset,
            "timestamp": timestamp,
            "scraped_at": datetime.now().isoformat(),
            "status_code": status_code,
            "error_message": error_msg
        },
        "error_response": error_data
    }
    
    with open(error_file, 'w') as f:
        json.dump(enriched_error, f, indent=2)
    
    print(f"  ✗ Saved error to: {error_file}")
    return error_file


def get_existing_pages(output_folder: Path, category_name: str) -> List[int]:
    """Get list of existing page numbers for a category"""
    category_name = sanitize_filename(category_name)
    pattern = f"{category_name}_page_*.json"
    existing_files = list(output_folder.glob(pattern))
    
    existing_pages = []
    for file_path in existing_files:
        try:
            # Extract page number from filename
            filename = file_path.stem
            if "_page_" in filename:
                page_part = filename.split("_page_")[1]
                page_no = int(page_part)
                existing_pages.append(page_no)
        except (ValueError, IndexError):
            continue
    
    return sorted(existing_pages)


def get_next_page_to_scrape(output_folder: Path, category_name: str) -> int:
    """Determine the next page number to scrape for resumable operation"""
    existing_pages = get_existing_pages(output_folder, category_name)
    
    if not existing_pages:
        return 0  # Start from page 0
    
    # Check if the last page has hasMore=False (category complete)
    last_page = max(existing_pages)
    category_name_safe = sanitize_filename(category_name)
    last_page_file = output_folder / f"{category_name_safe}_page_{last_page}.json"
    
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


def count_products_in_response(response_data: Dict[str, Any]) -> int:
    """Count products in a category listing response"""
    data = response_data.get("data", {})
    widgets = data.get("widgets", [])
    
    total_products = 0
    for widget in widgets:
        if widget.get("@type") == "type.googleapis.com/swiggy.gandalf.widgets.v2.GridWidget":
            grid_elements = widget.get("gridElements", {})
            info_list = grid_elements.get("infoWithStyle", {}).get("info", [])
            total_products += len(info_list)
    
    return total_products


def scrape_category_with_pagination(config: Dict[str, Any], category: Dict[str, Any], output_folder: Path, errors_folder: Path, resume: bool = True) -> Tuple[int, int]:
    """Scrape all pages of a category until hasMore is False"""
    max_retries = 5  # Increased from 3 to 5
    consecutive_rate_limits = 0
    total_products_scraped = 0
    pages_scraped = 0
    
    # Determine starting page for resumable operation
    if resume:
        start_page = get_next_page_to_scrape(output_folder, category["category_name"])
        existing_pages = get_existing_pages(output_folder, category["category_name"])
        
        # Check if category is already complete
        if start_page == -1:
            print(f"  ✅ Category {category['category_name']} already complete, skipping")
            # Count products from existing pages
            for page_no in existing_pages:
                try:
                    category_name = sanitize_filename(category["category_name"])
                    existing_file = output_folder / f"{category_name}_page_{page_no}.json"
                    if existing_file.exists():
                        with open(existing_file, 'r') as f:
                            existing_data = json.load(f)
                            total_products_scraped += count_products_in_response(existing_data.get("raw_response", {}))
                            pages_scraped += 1
                except Exception as e:
                    print(f"    ⚠️  Error reading existing page {page_no}: {e}")
            return pages_scraped, total_products_scraped
        
        if existing_pages and start_page > 0:
            print(f"  🔄 Resuming from page {start_page} (found existing pages: {existing_pages})")
            
            # Count products from existing pages
            for page_no in existing_pages:
                try:
                    category_name = sanitize_filename(category["category_name"])
                    existing_file = output_folder / f"{category_name}_page_{page_no}.json"
                    if existing_file.exists():
                        with open(existing_file, 'r') as f:
                            existing_data = json.load(f)
                            total_products_scraped += count_products_in_response(existing_data.get("raw_response", {}))
                            pages_scraped += 1
                except Exception as e:
                    print(f"    ⚠️  Error reading existing page {page_no}: {e}")
        else:
            print(f"  🆕 Starting fresh scrape from page 0")
    else:
        start_page = 0
    
    page_no = start_page
    offset = 0  # Will be updated from API response
    
    while True:
        print(f"\n  📄 Scraping page {page_no} for {category['category_name']}")
        
        # Retry loop with exponential backoff
        retry_attempt = 0
        success = False
        
        while retry_attempt < max_retries and not success:
            try:
                response_data, status_code, error_msg = make_category_listing_request(config, category, page_no, offset)
                
                if error_msg and is_rate_limited(status_code, error_msg):
                    # Rate limited - use exponential backoff
                    consecutive_rate_limits += 1
                    retry_attempt += 1
                    
                    if retry_attempt < max_retries:
                        backoff_delay = exponential_backoff(consecutive_rate_limits, base_delay=15.0)
                        time.sleep(backoff_delay)
                        continue
                    else:
                        # Max retries reached - save as error
                        print(f"    ❌ Max retries reached for page {page_no}")
                        save_error_response(errors_folder, category, response_data, page_no, offset, status_code, error_msg)
                        return pages_scraped, total_products_scraped
                
                elif error_msg:
                    # Non-rate-limit error - save and stop
                    save_error_response(errors_folder, category, response_data, page_no, offset, status_code, error_msg)
                    return pages_scraped, total_products_scraped
                
                else:
                    # Successful request
                    save_category_page_response(output_folder, category, response_data, page_no, offset, status_code)
                    consecutive_rate_limits = 0  # Reset rate limit counter
                    success = True
                    pages_scraped += 1
                    
                    # Check pagination info
                    data = response_data.get("data", {})
                    has_more = data.get("hasMore", False)
                    next_offset = data.get("offset", offset)
                    
                    # Count products in this page
                    page_products = count_products_in_response(response_data)
                    total_products_scraped += page_products
                    
                    print(f"    ✓ Page {page_no}: {page_products} products, hasMore: {has_more}")
                    
                    if not has_more:
                        print(f"    🏁 Finished scraping {category['category_name']} - no more pages")
                        return pages_scraped, total_products_scraped
                    
                    # Setup for next page
                    page_no += 1
                    offset = next_offset
                    break
                    
            except Exception as e:
                print(f"    ❌ Failed to process page {page_no}: {e}")
                return pages_scraped, total_products_scraped
        
        # Add delay between pages
        delay = config.get("delay_between_requests", 15.0)
        if consecutive_rate_limits > 0:
            delay *= (1 + consecutive_rate_limits * 0.5)
        
        print(f"    ⏱️  Waiting {delay:.1f}s before next page...")
        time.sleep(delay)


def setup_base_folders(config: Dict[str, Any]) -> Tuple[Path, Path, Path, Path, Path]:
    """Create base folder structure"""
    responses_folder = Path(config["responses_folder"])
    raw_folder = responses_folder / "raw"
    categories_folder = raw_folder / "categories"
    categories_all_folder = raw_folder / "categories-all"
    discovered_folder = raw_folder / "discovered_categories"
    errors_folder = responses_folder / "errors"
    
    # Create folders if they don't exist
    responses_folder.mkdir(exist_ok=True)
    raw_folder.mkdir(exist_ok=True)
    categories_folder.mkdir(exist_ok=True)
    categories_all_folder.mkdir(exist_ok=True)
    discovered_folder.mkdir(exist_ok=True)
    errors_folder.mkdir(exist_ok=True)
    
    return responses_folder, categories_folder, categories_all_folder, discovered_folder, errors_folder


def is_category_fully_scraped(categories_all_folder: Path, category_name: str) -> bool:
    """Check if a category has been fully scraped (hasMore=False on last page)"""
    existing_pages = get_existing_pages(categories_all_folder, category_name)
    
    if not existing_pages:
        return False
    
    # Check if the last page has hasMore=False
    last_page = max(existing_pages)
    category_name_safe = sanitize_filename(category_name)
    last_page_file = categories_all_folder / f"{category_name_safe}_page_{last_page}.json"
    
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


def copy_categories_to_all_folder(categories_folder: Path, categories_all_folder: Path):
    """Copy all category files from categories to categories-all folder"""
    copied_count = 0
    
    for category_file in categories_folder.glob("*.json"):
        dest_file = categories_all_folder / category_file.name
        
        if not dest_file.exists():
            # Read the original file and convert to paginated format
            try:
                with open(category_file, 'r') as f:
                    data = json.load(f)
                
                # Extract category name from metadata
                category_name = data.get("metadata", {}).get("category_name", "")
                if category_name:
                    # Save as page 0 in categories-all
                    category_name_safe = sanitize_filename(category_name)
                    new_filename = f"{category_name_safe}_page_0.json"
                    new_file = categories_all_folder / new_filename
                    
                    # Update metadata to include page info
                    if "metadata" in data:
                        data["metadata"]["page_no"] = 0
                        data["metadata"]["offset"] = 0
                    
                    with open(new_file, 'w') as f:
                        json.dump(data, f, indent=2)
                    
                    copied_count += 1
                    print(f"  📋 Copied {category_file.name} → {new_filename}")
                
            except Exception as e:
                print(f"  ❌ Error copying {category_file.name}: {e}")
    
    print(f"✓ Copied {copied_count} category files to categories-all folder")
    return copied_count
