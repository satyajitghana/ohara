import httpx
import json
import asyncio
from datetime import datetime
import os

async def scrape_listings_from_categories():
    """
    Reads categories from a JSON file, scrapes the product listings for each,
    and saves the raw and parsed data.
    """
    
    categories_filepath = os.path.join("responses", "categories.json")
    if not os.path.exists(categories_filepath):
        print(f"❌ ERROR: Cannot find categories file at {categories_filepath}")
        print("Please run the scrape_categories.py script first.")
        return

    with open(categories_filepath, 'r', encoding='utf-8') as f:
        categories = json.load(f)

    print(f"Found {len(categories)} categories to scrape.")

    # Create directories if they don't exist
    os.makedirs("responses/raw", exist_ok=True)
    os.makedirs("responses/listings", exist_ok=True)
    os.makedirs("responses/errors", exist_ok=True)

    headers = {
        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'x-build-version': '2.291.0'
    }

    async with httpx.AsyncClient(timeout=30.0) as client:
        for category in categories:
            params = category.get("link_params")
            if not params or not params.get("categoryName"):
                print(f"⚠️  Skipping category due to missing link_params: {category.get('description')}")
                continue
            
            # Add a small delay between categories
            await asyncio.sleep(2)

            # Add primaryStoreId which is required by the API but might be missing in the deeplink
            params['primaryStoreId'] = params.get('storeId')
            params['secondaryStoreId'] = ''

            url = "https://www.swiggy.com/api/instamart/category-listing"
            category_name = params.get("categoryName").replace(" ", "_").replace("&", "and")

            try:
                print(f"- Scraping category: {params.get('categoryName')}")
                
                all_products = []
                current_offset = 0
                page_no = 0
                has_more = True

                while has_more:
                    try:
                        # Add a small delay between page requests
                        if page_no > 0:
                            await asyncio.sleep(1)

                        paginated_url = "https://www.swiggy.com/api/instamart/category-listing"
                        paginated_params = params.copy() # Start with base params
                        paginated_params['offset'] = current_offset
                        paginated_params['pageNo'] = page_no

                        response = await client.get(paginated_url, headers=headers, params=paginated_params)
                        response.raise_for_status()
                        
                        try:
                            data = response.json()
                        except json.JSONDecodeError:
                            print(f"  ⚠️  Could not decode JSON for page {page_no}. Saving error response.")
                            error_filename = f"error_{category_name}_page_{page_no}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                            error_filepath = os.path.join("responses", "errors", error_filename)
                            with open(error_filepath, 'w', encoding='utf-8') as f:
                                f.write(response.text)
                            break # Move to the next category

                        # Save raw response for each page
                        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                        raw_filename = f"listing_{category_name}_page_{page_no}_{timestamp}.json"
                        raw_filepath = os.path.join("responses", "raw", raw_filename)
                        with open(raw_filepath, 'w', encoding='utf-8') as f:
                            json.dump(data, f, indent=2, ensure_ascii=False)
                        print(f"  - Saved raw response for page {page_no} to {raw_filepath}")

                        # --- Recursively find and extract product data ---
                        def find_products_recursively(data_blob):
                            products = []
                            if isinstance(data_blob, dict):
                                # If we find a product list, process it
                                if data_blob.get("widgetInfo", {}).get("widgetType") == "PRODUCT_LIST":
                                    items = data_blob.get("data", [])
                                    if isinstance(items, list):
                                        for item in items:
                                            if item and isinstance(item, dict) and item.get("variations"):
                                                products.append(item)
                                # Otherwise, continue searching deeper
                                else:
                                    for key, value in data_blob.items():
                                        products.extend(find_products_recursively(value))
                            elif isinstance(data_blob, list):
                                for item in data_blob:
                                    products.extend(find_products_recursively(item))
                            return products

                        found_items = find_products_recursively(data)
                        
                        for item in found_items:
                            product_info = {
                                "display_name": item.get("display_name"),
                                "brand": item.get("brand"),
                                "brand_id": item.get("brand_id"),
                                "product_id": item.get("product_id"),
                                "variations": []
                            }
                            
                            for var in item.get("variations", []):
                                variation_details = {
                                    "id": var.get("id"),
                                    "display_name": var.get("display_name"),
                                    "price_mrp": var.get("price", {}).get("mrp"),
                                    "brand": var.get("brand"),
                                    "brand_id": var.get("brand_id"),
                                    "category": var.get("category"),
                                    "super_category": var.get("super_category"),
                                    "sub_category_l3": var.get("sub_category_l3"),
                                    "sub_category_l4": var.get("sub_category_l4"),
                                    "sub_category_l5": var.get("sub_category_l5"),
                                    "product_name_without_brand": var.get("product_name_without_brand"),
                                    "images": var.get("images"),
                                    "images_v2": var.get("images_v2"),
                                    "quantity": var.get("quantity"),
                                    "sku_quantity_with_combo": var.get("sku_quantity_with_combo"),
                                    "unit_of_measure": var.get("unit_of_measure"),
                                    "weight_in_grams": var.get("weight_in_grams"),
                                    "volumetric_weight": var.get("volumetric_weight"),
                                    "filters_tag": var.get("filters_tag")
                                }
                                product_info["variations"].append(variation_details)
                            
                            all_products.append(product_info)

                        # Update pagination variables
                        has_more = data.get("data", {}).get("hasMore", False)
                        current_offset = data.get("data", {}).get("offset", current_offset)
                        page_no += 1
                    
                    except httpx.HTTPStatusError as e:
                        print(f"  ❌ HTTP ERROR for {params.get('categoryName')}: {e.response.status_code}. Saving error response.")
                        error_filename = f"error_{category_name}_page_{page_no}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html"
                        error_filepath = os.path.join("responses", "errors", error_filename)
                        with open(error_filepath, 'w', encoding='utf-8') as f:
                            f.write(e.response.text)
                    except Exception as e:
                        print(f"  ❌ An unexpected error occurred for {params.get('categoryName')}: {e}")
                
                # --- Save all parsed data for the category ---
                parsed_filename = f"{category_name}.json"
                parsed_filepath = os.path.join("responses", "listings", parsed_filename)
                with open(parsed_filepath, 'w', encoding='utf-8') as f:
                    json.dump(all_products, f, indent=2, ensure_ascii=False)
                print(f"  - Saved {len(all_products)} total parsed products to {parsed_filepath}")

            except Exception as e:
                print(f"  ❌ An unexpected error occurred for {params.get('categoryName')}: {e}")
    
    print("\n✅ Scraping complete.")

if __name__ == "__main__":
    asyncio.run(scrape_listings_from_categories())
