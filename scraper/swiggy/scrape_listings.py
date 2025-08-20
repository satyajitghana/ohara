import asyncio
from pathlib import Path
from utils.config import get_api_config, get_directories_config
from utils.http_client import create_http_client, get_default_headers
from utils.file_operations import (
    ensure_directories_exist, save_json, load_json, 
    get_timestamped_filename, save_error_response
)
from utils.data_processing import find_products_recursively, format_product_info, should_include_product
from utils.console_utils import (
    print_success, print_error, print_warning, print_info, print_banner,
    create_header, get_console, get_progress_bar, create_summary_table, log_message
)

async def scrape_listings_from_categories():
    """
    Reads categories from a JSON file, scrapes the product listings for each,
    and saves the raw and parsed data.
    """
    console = get_console()
    
    # Print beautiful header
    header = create_header(
        "📦 Swiggy Product Listings Scraper", 
        "Extracting product data from all categories"
    )
    console.print(header)
    
    directories = get_directories_config()
    api_config = get_api_config()
    
    categories_filepath = Path(directories['responses']) / "categories.json"
    if not categories_filepath.exists():
        print_error("Categories file not found", f"Path: {categories_filepath}")
        print_info("Please run scrape_categories.py first")
        return

    categories = load_json(categories_filepath)
    print_info("Categories loaded", f"Found {len(categories)} categories to process")

    # Create directories if they don't exist
    ensure_directories_exist(directories)
    
    headers = get_default_headers()
    total_products = 0
    successful_categories = 0
    
    print_banner("Starting Category Processing")

    async with await create_http_client() as client:
        with get_progress_bar(show_speed=False) as overall_progress:
            main_task = overall_progress.add_task(
                "[bold green]Processing categories...", 
                total=len(categories)
            )
            for category in categories:
                params = category.get("link_params")
                if not params or not params.get("categoryName"):
                    log_message("Skipping category - missing params", "warning")
                    overall_progress.update(main_task, advance=1)
                    continue
                
                category_name_raw = params.get("categoryName")
                category_name = category_name_raw.replace(" ", "_").replace("&", "and")
                
                # Add a small delay between categories
                await asyncio.sleep(2)

                # Add primaryStoreId which is required by the API but might be missing in the deeplink
                params['primaryStoreId'] = params.get('storeId')
                params['secondaryStoreId'] = ''

                url = f"{api_config['base_url']}/category-listing"

                try:
                    log_message(f"Processing: {category_name_raw}", "info")
                    
                    all_products = []
                    current_offset = 0
                    page_no = 0
                    has_more = True

                    # Create sub-progress for pages within this category
                    page_task = overall_progress.add_task(
                        f"[cyan]  └─ {category_name_raw[:30]}...", 
                        total=None
                    )

                    while has_more:
                        try:
                            # Add a small delay between page requests
                            if page_no > 0:
                                await asyncio.sleep(1)

                            paginated_params = params.copy()  # Start with base params
                            paginated_params['offset'] = current_offset
                            paginated_params['pageNo'] = page_no

                            response = await client.get(url, headers=headers, params=paginated_params)
                            response.raise_for_status()
                            
                            try:
                                data = response.json()
                            except Exception:
                                log_message(f"JSON decode error on page {page_no}", "warning")
                                save_error_response(response.text, category_name, page_no, directories['errors'])
                                break  # Move to the next category

                            # Save raw response for each page
                            raw_filename = get_timestamped_filename(f"listing_{category_name}_page_{page_no}")
                            raw_filepath = Path(directories['raw']) / raw_filename
                            save_json(data, raw_filepath)

                            # Find and extract product data
                            found_items = find_products_recursively(data)
                            
                            for item in found_items:
                                product_info = format_product_info(item)
                                # Only include products that have at least one non-combo variation
                                if should_include_product(product_info):
                                    all_products.append(product_info)

                            # Update page progress
                            overall_progress.update(
                                page_task, 
                                description=f"[cyan]  └─ {category_name_raw[:30]}... (page {page_no + 1}, {len(all_products)} products)"
                            )

                            # Update pagination variables
                            has_more = data.get("data", {}).get("hasMore", False)
                            current_offset = data.get("data", {}).get("offset", current_offset)
                            page_no += 1
                        
                        except Exception as e:
                            log_message(f"Page error: {str(e)}", "error")
                            if hasattr(e, 'response'):
                                save_error_response(e.response.text, category_name, page_no, directories['errors'])
                            break
                    
                    # Save all parsed data for the category
                    parsed_filename = f"{category_name}.json"
                    parsed_filepath = Path(directories['listings']) / parsed_filename
                    save_json(all_products, parsed_filepath)
                    
                    total_products += len(all_products)
                    successful_categories += 1
                    
                    # Remove the page task and update main progress
                    overall_progress.remove_task(page_task)
                    overall_progress.update(main_task, advance=1)
                    
                    log_message(f"Completed {category_name_raw}: {len(all_products)} products", "success")

                except Exception as e:
                    log_message(f"Category error: {str(e)}", "error")
                    overall_progress.update(main_task, advance=1)
    
    # Final summary
    print_banner("Scraping Complete")
    stats = {
        "Total Categories Processed": successful_categories,
        "Total Products Found": total_products,
        "Success Rate": f"{(successful_categories/len(categories)*100):.1f}%"
    }
    console.print(create_summary_table(stats))
    print_success("All categories processed successfully")

if __name__ == "__main__":
    asyncio.run(scrape_listings_from_categories())
