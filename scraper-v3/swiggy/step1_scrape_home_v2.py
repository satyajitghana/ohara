#!/usr/bin/env python3
"""
Step 1: Swiggy Home API Scraper v2
Fetches category data from Swiggy's home API and saves the results.
"""

import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from utils.common import load_config, save_json, print_category_summary
from utils.api import fetch_swiggy_home_api, extract_categories_from_response


def main():
    """Main function to fetch and process Swiggy home API."""
    print("🚀 Starting Swiggy Home API Scraper v2...")
    
    try:
        # Load configuration
        config = load_config()
        output_config = config['output']
        
        # You can specify a different store here if needed
        # Check if store name is provided as command line argument
        store_name = "default"
        if len(sys.argv) > 1:
            store_name = sys.argv[1]
            print(f"📍 Using store: {store_name}")
        else:
            print(f"📍 Using default store (pass store name as argument to use different store)")
        
        # Fetch the home API response
        api_response = fetch_swiggy_home_api(store_name)
        
        if not api_response:
            print("❌ Failed to fetch API response. Exiting.")
            return 1
        
        # Create output directory
        responses_dir = Path(output_config['base_directory'])
        responses_dir.mkdir(exist_ok=True)
        print(f"📁 Created/verified {responses_dir} directory")
        
        # Save the raw API response for debugging
        raw_response_path = responses_dir / output_config['raw_home_api_filename']
        save_json(api_response, raw_response_path)
        print(f"💾 Raw API response saved to {raw_response_path}")
        
        # Extract categories from the response
        print("\n🔍 Extracting categories from API response...")
        categories = extract_categories_from_response(api_response)
        
        if categories:
            # Save extracted categories
            output_path = responses_dir / output_config['home_api_filename']
            output_data = {
                'total_categories': len(categories),
                'store_name': store_name,
                'extracted_at': api_response.get('data', {}).get('pageOffset', {}).get('nextOffset', ''),
                'categories': categories
            }
            
            save_json(output_data, output_path)
            
            print(f"\n✅ SUCCESS: Extracted {len(categories)} categories")
            print(f"💾 Data saved to {output_path}")
            
            # Print detailed summary
            print_category_summary(categories)
            
            print(f"\n🎯 Next Step:")
            print(f"   Run: python step2_scrape_categories.py")
            print(f"   This will scrape each category's listing pages")
                
        else:
            print("❌ No categories found in the API response")
            return 1
        
        return 0
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
