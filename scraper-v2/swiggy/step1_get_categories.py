#!/usr/bin/env python3
"""
Step 1: Get all categories from Swiggy home page
This script fetches the home page categories and extracts category information.
"""

import json
import requests
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any


def load_config() -> Dict[str, Any]:
    """Load configuration from config-v2.json"""
    # Look for config in current dir, then parent dirs
    config_path = Path("config-v2.json")
    if not config_path.exists():
        config_path = Path("config-v2.json")
    if not config_path.exists():
        raise FileNotFoundError("config-v2.json not found. Please create it in the project root.")
    
    with open(config_path, 'r') as f:
        return json.load(f)


def setup_folders(config: Dict[str, Any]) -> Path:
    """Create necessary folders using pathlib"""
    # Create responses folder relative to project root
    responses_folder = Path(".") / config["responses_folder"]
    raw_folder = responses_folder / "raw"
    
    # Create folders if they don't exist
    responses_folder.mkdir(exist_ok=True)
    raw_folder.mkdir(exist_ok=True)
    
    print(f"✓ Created folder structure: {responses_folder}")
    return responses_folder


def make_request(config: Dict[str, Any]) -> Dict[str, Any]:
    """Make request to Swiggy home API"""
    base_url = config["base_url"]
    endpoint = config["api_endpoints"]["home_v2"]
    headers = config["headers"]
    cookies_str = config["cookies"]
    params = config["default_params"]
    
    # Convert cookies string to dict
    cookies = {}
    for cookie in cookies_str.split('; '):
        if '=' in cookie:
            key, value = cookie.split('=', 1)
            cookies[key] = value
    
    url = f"{base_url}{endpoint}"
    
    print(f"Making request to: {url}")
    print(f"Parameters: {params}")
    
    try:
        response = requests.get(
            url,
            headers=headers,
            cookies=cookies,
            params=params,
            timeout=30
        )
        response.raise_for_status()
        
        print(f"✓ Request successful! Status: {response.status_code}")
        return response.json()
        
    except requests.exceptions.RequestException as e:
        print(f"✗ Request failed: {e}")
        raise


def extract_categories(response_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract categories from the API response"""
    categories = []
    
    # Navigate through the response structure
    if "data" not in response_data or "cards" not in response_data["data"]:
        print("✗ Unexpected response structure")
        return categories
    
    cards = response_data["data"]["cards"]
    print(f"Found {len(cards)} cards in response")
    
    for card_idx, card_wrapper in enumerate(cards):
        if "card" not in card_wrapper or "card" not in card_wrapper["card"]:
            continue
            
        card = card_wrapper["card"]["card"]
        
        # Look for GridWidget cards that contain categories
        if card.get("@type") == "type.googleapis.com/swiggy.gandalf.widgets.v2.GridWidget":
            grid_elements = card.get("gridElements", {})
            info_with_style = grid_elements.get("infoWithStyle", {})
            info_list = info_with_style.get("info", [])
            
            if info_list:
                widget_id = card.get("id", "unknown")
                header_title = card.get("header", {}).get("title", "Unknown Category Group")
                print(f"  Processing widget {widget_id}: '{header_title}' with {len(info_list)} items")
                
                for item in info_list:
                    category_info = extract_category_info(item, widget_id, header_title)
                    if category_info:
                        categories.append(category_info)
    
    print(f"✓ Extracted {len(categories)} categories total")
    return categories


def extract_category_info(item: Dict[str, Any], widget_id: str, category_group: str) -> Dict[str, Any]:
    """Extract individual category information"""
    category = {}
    
    # Basic info
    category["id"] = item.get("id", "")
    category["imageId"] = item.get("imageId", "")
    category["category_name"] = item.get("description", "")  # description is actually the category name
    category["widget_id"] = widget_id
    category["category_group"] = category_group
    
    # Extract action/deeplink
    action = item.get("action", {})
    if action:
        category["deeplink"] = action.get("link", "")
        category["action_type"] = action.get("type", "")
    
    # Extract analytics info
    analytics = item.get("analytics", {})
    if analytics:
        extra_fields = analytics.get("extraFields", {})
        category["l1_node_val"] = extra_fields.get("l1NodeVal", "")
    
    # Only return if we have essential data
    if category["category_name"] and category["imageId"]:
        return category
    
    return None


def save_responses(responses_folder: Path, raw_response: Dict[str, Any], categories: List[Dict[str, Any]]):
    """Save both raw response and processed categories"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # Save raw response
    raw_file = responses_folder / "raw" / f"home_v2_{timestamp}.json"
    with open(raw_file, 'w') as f:
        json.dump(raw_response, f, indent=2)
    print(f"✓ Saved raw response to: {raw_file}")
    
    # Save processed categories
    categories_file = responses_folder / "home.json"
    output_data = {
        "timestamp": timestamp,
        "total_categories": len(categories),
        "categories": categories
    }
    
    with open(categories_file, 'w') as f:
        json.dump(output_data, f, indent=2)
    print(f"✓ Saved processed categories to: {categories_file}")
    
    # Print summary
    print(f"\n📊 SUMMARY:")
    print(f"   Total categories found: {len(categories)}")
    
    # Group by category group
    by_group = {}
    for cat in categories:
        group = cat["category_group"]
        if group not in by_group:
            by_group[group] = 0
        by_group[group] += 1
    
    for group, count in by_group.items():
        print(f"   - {group}: {count} categories")


def main():
    """Main function"""
    print("🚀 Starting Step 1: Get Categories from Swiggy Home Page")
    print("=" * 60)
    
    try:
        # Load config
        config = load_config()
        print("✓ Loaded configuration")
        
        # Setup folders
        responses_folder = setup_folders(config)
        
        # Make request
        response_data = make_request(config)
        
        # Extract categories
        categories = extract_categories(response_data)
        
        # Save results
        save_responses(responses_folder, response_data, categories)
        
        print("\n✅ Step 1 completed successfully!")
        
        # Add delay to avoid rate limiting
        delay = config.get("delay_between_requests", 1.0)
        if delay > 0:
            print(f"⏱️  Waiting {delay}s to avoid rate limiting...")
            time.sleep(delay)
            
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise


if __name__ == "__main__":
    main()
