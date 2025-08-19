import httpx
import json
import asyncio
from datetime import datetime
import os
from urllib.parse import urlparse, parse_qs

async def scrape_swiggy_categories():
    """
    Scrapes Swiggy Instamart for categories from the entrypoint API,
    extracts relevant details, and saves the output.
    """
    # API details from the user's curl command
    url = "https://www.swiggy.com/api/instamart/home/v2"
    params = {
        'offset': '1',
        'layoutId': '4987',
        'storeId': '1313712',
        'primaryStoreId': '1313712',
        'secondaryStoreId': '',
        'clientId': 'INSTAMART-APP'
    }
    
    headers = {
        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'x-build-version': '2.291.0'
    }
    
    print("🚀 Starting Swiggy Instamart category scraper...")
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"🔗 Calling API: {url}")
            response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()  # Raise an exception for bad status codes
            
            print(f"✅ SUCCESS! API returned status code: {response.status_code}")
            data = response.json()
            
            # --- Save the full response ---
            os.makedirs("responses/raw", exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            full_response_filename = f"swiggy_entrypoint_{timestamp}.json"
            full_response_filepath = os.path.join("responses/raw", full_response_filename)
            
            with open(full_response_filepath, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            print(f"💾 Full response saved to: {full_response_filepath}")

            # --- Parse and extract category data ---
            categories = []
            
            # The data is deeply nested, so we need to traverse it carefully.
            for card in data.get("data", {}).get("cards", []):
                grid_elements = card.get("card", {}).get("card", {}).get("gridElements", {})
                if grid_elements:
                    info_with_style = grid_elements.get("infoWithStyle", {})
                    if info_with_style:
                        items = info_with_style.get("info", [])
                        for item in items:
                            action = item.get("action", {})
                            link = action.get("link")
                            
                            if link and "category-listing" in link:
                                try:
                                    parsed_url = urlparse(link)
                                    query_params = parse_qs(parsed_url.query)
                                    
                                    category_info = {
                                        "imageId": item.get("imageId"),
                                        "description": item.get("description"),
                                        "link": link,
                                        "link_params": {
                                            "categoryName": query_params.get("categoryName", [None])[0],
                                            "storeId": query_params.get("storeId", [None])[0],
                                            "offset": query_params.get("offset", [None])[0],
                                            "filterName": query_params.get("filterName", [None])[0],
                                            "taxonomyType": query_params.get("taxonomyType", [None])[0],
                                        }
                                    }
                                    categories.append(category_info)
                                except Exception as e:
                                    print(f"⚠️  Could not parse link: {link} - Error: {e}")

            print(f"📊 Extracted {len(categories)} categories.")

            # --- Save the extracted categories ---
            categories_filepath = os.path.join("responses", "categories.json")
            with open(categories_filepath, 'w', encoding='utf-8') as f:
                json.dump(categories, f, indent=2, ensure_ascii=False)
            
            print(f"💾 Extracted categories saved to: {categories_filepath}")
            
            return categories_filepath

        except httpx.HTTPStatusError as e:
            print(f"❌ HTTP ERROR: {e.response.status_code} - {e.response.text[:200]}...")
            return None
        except Exception as e:
            print(f"❌ An unexpected error occurred: {e}")
            return None

if __name__ == "__main__":
    asyncio.run(scrape_swiggy_categories())
