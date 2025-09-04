#!/usr/bin/env python3
"""
Common utility functions for Swiggy scraper.
"""

import json
import re
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlencode
from typing import Dict, Any, Optional, List


def load_config(config_path: str = "config.json") -> Dict[str, Any]:
    """Load configuration from JSON file."""
    try:
        config_file = Path(__file__).parent.parent / config_path
        with open(config_file, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading config from {config_path}: {e}")
        raise


def get_store_config(store_name: str = "default") -> Dict[str, Any]:
    """Get store configuration by name."""
    config = load_config()
    stores = config.get('stores', {})
    
    if store_name not in stores:
        print(f"⚠️ Store '{store_name}' not found in config, using default")
        store_name = "default"
    
    return stores.get(store_name, {})


def extract_store_id_from_url(url: str) -> Optional[str]:
    """Extract storeId parameter from a Swiggy deeplink URL."""
    try:
        if "storeId=" in url:
            parsed = urlparse(url)
            if parsed.query:
                params = parse_qs(parsed.query)
                return params.get('storeId', [None])[0]
    except Exception:
        pass
    return None


def convert_deeplink_to_web_url(deeplink: str) -> str:
    """Convert Swiggy deeplink to web URL format."""
    # Extract parameters from deeplink
    if "?" in deeplink:
        query_part = deeplink.split("?", 1)[1]
        params = {}
        for param_pair in query_part.split("&"):
            if "=" in param_pair:
                key, value = param_pair.split("=", 1)
                params[key] = value
        
        # Add custom_back parameter
        params['custom_back'] = 'true'
        
        # Build web URL
        base_url = "https://www.swiggy.com/instamart/category-listing"
        return f"{base_url}?{urlencode(params)}"
    
    return deeplink


def create_safe_filename(name: str) -> str:
    """Convert category name to safe filename."""
    return "".join(c for c in name if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')


def ensure_directory(directory: Path) -> None:
    """Ensure directory exists, create if necessary."""
    directory.mkdir(parents=True, exist_ok=True)


def save_json(data: Any, file_path: Path, indent: int = 2) -> None:
    """Save data as JSON file."""
    ensure_directory(file_path.parent)
    with open(file_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=indent, ensure_ascii=False)


def load_json(file_path: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file, return None if not found."""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        print(f"❌ Error loading JSON from {file_path}: {e}")
        return None


def extract_initial_state_from_html(html_content: str) -> Dict[str, Any]:
    """Extract ___INITIAL_STATE___ JSON from HTML content."""
    try:
        from bs4 import BeautifulSoup
        
        soup = BeautifulSoup(html_content, 'html.parser')
        initial_state_script = soup.find('script', string=re.compile(r'window\.___INITIAL_STATE___'))
        
        if initial_state_script:
            script_content = initial_state_script.string
            match = re.search(r'window\.___INITIAL_STATE___\s*=\s*(\{.*?\});', script_content, re.DOTALL)
            
            if match:
                json_text = match.group(1)
                return json.loads(json_text)
        
    except Exception as e:
        print(f"❌ Error extracting initial state: {e}")
    
    return {}


def print_summary_header(title: str) -> None:
    """Print a formatted header for summaries."""
    print(f"\n{'='*60}")
    print(f"  {title}")
    print(f"{'='*60}")


def print_category_summary(categories: list) -> None:
    """Print summary of extracted categories."""
    if not categories:
        print("❌ No categories found")
        return
    
    print_summary_header("CATEGORY EXTRACTION SUMMARY")
    print(f"✅ Total categories extracted: {len(categories)}")
    
    # Group by category group title
    groups = {}
    for cat in categories:
        group = cat.get('category_group_title', 'Unknown')
        if group not in groups:
            groups[group] = []
        groups[group].append(cat.get('category_name', 'Unknown'))
    
    print(f"\n📊 Category Groups:")
    for group, items in groups.items():
        print(f"   🏷️  {group}: {len(items)} categories")
        for item in items[:3]:  # Show first 3 items
            print(f"      - {item}")
        if len(items) > 3:
            print(f"      ... and {len(items) - 3} more")


def extract_filters_from_category_data(category_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract filters from category page data."""
    try:
        filters = category_data.get('data', {}).get('filters', [])
        print(f"📋 Found {len(filters)} filters in category data")
        
        valid_filters = []
        for f in filters:
            if f.get('id') and f.get('name') and f.get('type'):
                valid_filters.append(f)
                print(f"   ✅ {f['name']} (ID: {f['id']}, Products: {f.get('productCount', 0)})")
            else:
                print(f"   ⏭️ Skipping invalid filter: {f}")
        
        return valid_filters
    except Exception as e:
        print(f"❌ Error extracting filters: {e}")
        return []


def build_filter_url(category_name: str, filter_id: str, filter_name: str, filter_type: str, store_id: str = None) -> str:
    """Build URL for filter-specific category listing."""
    if not store_id:
        config = load_config()
        store_config = config['stores']['default']
        store_id = store_config['store_id']
    
    from urllib.parse import urlencode
    
    params = {
        'categoryName': category_name,
        'custom_back': 'true',
        'filterId': filter_id,
        'filterName': '',  # Keep empty as in the example
        'offset': '0',
        'showAgeConsent': 'false',
        'storeId': store_id,
        'taxonomyType': filter_type
    }
    
    base_url = "https://www.swiggy.com/instamart/category-listing"
    return f"{base_url}?{urlencode(params)}"


def print_directory_structure_summary(base_dir: Path) -> None:
    """Print summary of the scraped data directory structure."""
    if not base_dir.exists():
        print("❌ Output directory not found")
        return
    
    print_summary_header("OUTPUT DIRECTORY STRUCTURE")
    print(f"📁 Base directory: {base_dir}")
    
    # Check for home API files
    config = load_config()
    output_config = config['output']
    
    home_file = base_dir / output_config['home_api_filename']
    raw_home_file = base_dir / output_config['raw_home_api_filename']
    
    if home_file.exists():
        print(f"✅ Home API data: {home_file}")
    if raw_home_file.exists():
        print(f"✅ Raw home API data: {raw_home_file}")
    
    # Check categories directory
    categories_dir = base_dir / output_config['categories_subdirectory']
    if categories_dir.exists():
        category_folders = [d for d in categories_dir.iterdir() if d.is_dir()]
        print(f"✅ Categories directory: {categories_dir}")
        print(f"📊 Total category folders: {len(category_folders)}")
        
        if category_folders:
            print(f"\n📂 Category folders (showing first 5):")
            for folder in sorted(category_folders)[:5]:
                files = list(folder.glob("*"))
                filters_dir = folder / "filters"
                filter_count = 0
                if filters_dir.exists():
                    filter_folders = [d for d in filters_dir.iterdir() if d.is_dir()]
                    filter_count = len(filter_folders)
                
                print(f"   📁 {folder.name} ({len(files)} files, {filter_count} filters)")
                
            if len(category_folders) > 5:
                print(f"   ... and {len(category_folders) - 5} more folders")
    else:
        print(f"❌ Categories directory not found: {categories_dir}")


def load_categories_from_output(base_dir: Path) -> List[Dict[str, Any]]:
    """Load all available categories from the output directory."""
    config = load_config()
    categories_dir = base_dir / config['output']['categories_subdirectory']
    
    if not categories_dir.exists():
        print(f"❌ Categories directory not found: {categories_dir}")
        return []
    
    categories = []
    category_folders = [d for d in categories_dir.iterdir() if d.is_dir()]
    
    for folder in category_folders:
        page_0_file = folder / f"{folder.name}_page_0.json"
        if page_0_file.exists():
            category_data = load_json(page_0_file)
            if category_data:
                # Extract category info
                data = category_data.get('data', {})
                category_info = {
                    'category_name': data.get('selectedCategoryName', folder.name.replace('_', ' ')),
                    'category_id': data.get('selectedCategoryId', ''),
                    'folder_name': folder.name,
                    'filters': extract_filters_from_category_data(category_data)
                }
                categories.append(category_info)
            else:
                print(f"⚠️ Could not load data from {page_0_file}")
        else:
            print(f"⚠️ Missing page_0.json for category: {folder.name}")
    
    print(f"📋 Loaded {len(categories)} categories with filter data")
    return categories
