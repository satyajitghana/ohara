#!/usr/bin/env python3
"""
API-related utility functions for Swiggy scraper.
"""

import requests
from typing import Dict, Any, Optional, List
from urllib.parse import parse_qs, urlparse

from .common import load_config, get_store_config


def build_home_api_url() -> str:
    """Build the home API URL with parameters."""
    config = load_config()
    store_config = get_store_config()
    
    base_url = config['api']['base_url']
    endpoint = config['api']['home_endpoint']
    
    return f"{base_url}{endpoint}"


def build_home_api_params(store_name: str = "default") -> Dict[str, str]:
    """Build query parameters for home API request."""
    store_config = get_store_config(store_name)
    
    return {
        'offset': '1',
        'layoutId': store_config.get('layout_id', '4987'),
        'storeId': store_config.get('store_id', '1392080'),
        'primaryStoreId': store_config.get('primary_store_id', '1392080'),
        'secondaryStoreId': store_config.get('secondary_store_id', '1396284'),
        'clientId': 'INSTAMART-APP'
    }


def get_api_headers() -> Dict[str, str]:
    """Get API headers from config."""
    config = load_config()
    return config.get('headers', {})


def get_api_cookies() -> Dict[str, str]:
    """Get API cookies from config."""
    config = load_config()
    return config.get('cookies', {})


def fetch_swiggy_home_api(store_name: str = "default") -> Optional[Dict[str, Any]]:
    """Fetch categories from Swiggy's home API."""
    config = load_config()
    timeout = config['timeouts']['api_request_timeout']
    
    url = build_home_api_url()
    params = build_home_api_params(store_name)
    headers = get_api_headers()
    cookies = get_api_cookies()
    
    print("🚀 Fetching Swiggy home API...")
    print(f"   Store: {store_name}")
    print(f"   URL: {url}")
    print(f"   Store ID: {params['storeId']}")
    
    try:
        response = requests.get(
            url, 
            params=params, 
            headers=headers, 
            cookies=cookies, 
            timeout=timeout
        )
        
        if response.status_code == 200:
            print("✅ Successfully fetched home API response")
            return response.json()
        else:
            print(f"❌ API request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error occurred: {e}")
        return None


def extract_categories_from_response(api_response: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Extract category information from the Swiggy home API response.
    This version is more robust and handles cases where GridWidgets might be missing
    headers or other expected keys, which can happen with banner widgets.
    """
    categories = []
    
    try:
        data = api_response.get('data', {})
        cards = data.get('cards', [])
        
        print(f"Processing {len(cards)} cards from API response...")
        
        for card_index, card in enumerate(cards):
            # The actual card data can be nested one level down
            card_data = card.get('card', {}).get('card', {})
            card_type = card_data.get('@type', '')
            
            # We are only interested in GridWidgets that represent categories
            if card_type != 'type.googleapis.com/swiggy.gandalf.widgets.v2.GridWidget':
                continue

            # A valid category group must have a header with a title
            header = card_data.get('header')
            if not header or not header.get('title'):
                print(f"  -> Skipping GridWidget without a valid header title (likely a banner).")
                continue

            category_group_title = header.get('title')
            
            # The categories themselves are inside gridElements.infoWithStyle.info
            grid_elements = card_data.get('gridElements')
            if not grid_elements:
                continue
                
            info_with_style = grid_elements.get('infoWithStyle')
            if not info_with_style:
                continue

            info_items = info_with_style.get('info', [])
            if not info_items:
                continue

            print(f"  -> Found GridWidget '{category_group_title}' with {len(info_items)} items.")

            for item in info_items:
                action = item.get('action', {})
                link = action.get('link', '')
                
                # A valid category item must have a category-listing deeplink
                if 'swiggy://stores/instamart/category-listing' in link:
                    category_name = item.get('description')
                    if not category_name:
                        # Fallback for older formats or variations
                        parsed_link = urlparse(link)
                        query_params = parse_qs(parsed_link.query)
                        category_name = query_params.get('categoryName', [None])[0]
                    
                    if not category_name:
                        print(f"    ⏭️  Skipping item with no category name.")
                        continue

                    from .common import extract_store_id_from_url
                    store_id = extract_store_id_from_url(link)
                    
                    category_info = {
                        'category_group_title': category_group_title,
                        'category_name': category_name,
                        'deeplink': link,
                        'store_id': store_id,
                        'widget_id': card_data.get('id', ''),
                        'image_id': item.get('imageId', ''),
                        'item_id': item.get('id', ''),
                        'analytics_l1_node': item.get('analytics', {}).get('extraFields', {}).get('l1NodeVal', '')
                    }
                    
                    categories.append(category_info)
                    print(f"    ✅ Found category: {category_name} (Group: {category_group_title})")
        
    except Exception as e:
        print(f"❌ Error parsing response: {e}")
        import traceback
        traceback.print_exc()
    
    return categories
