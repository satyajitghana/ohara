import asyncio
from pathlib import Path
from utils.config import get_api_config, get_default_params, get_directories_config
from utils.http_client import create_http_client, make_api_request
from utils.file_operations import ensure_directories_exist, save_json, get_timestamped_filename
from utils.data_processing import extract_categories_from_response
from utils.console_utils import (
    print_success, print_error, print_info, print_banner, 
    create_header, get_console, create_summary_table
)

async def scrape_swiggy_categories():
    """
    Scrapes Swiggy Instamart for categories from the entrypoint API,
    extracts relevant details, and saves the output.
    """
    console = get_console()
    
    # Print beautiful header
    header = create_header(
        "🏪 Swiggy Category Scraper", 
        "Extracting product categories from Swiggy Instamart"
    )
    console.print(header)
    
    api_config = get_api_config()
    directories = get_directories_config()
    default_params = get_default_params()
    
    # API details
    url = f"{api_config['base_url']}/home/v2"
    params = default_params.copy()
    
    print_info("Initializing scraper", f"Target: {url}")
    
    # Ensure directories exist
    ensure_directories_exist(directories)
    print_info("Directory structure created")
    
    async with await create_http_client() as client:
        try:
            print_banner("Making API Request")
            response = await make_api_request(client, url, params)
            
            print_success("API request successful", f"Status: {response.status_code}")
            data = response.json()
            
            # Save the full response
            full_response_filename = get_timestamped_filename("swiggy_entrypoint")
            full_response_filepath = Path(directories['raw']) / full_response_filename
            save_json(data, full_response_filepath)
            print_info("Raw response saved", f"File: {full_response_filename}")

            # Parse and extract category data
            print_banner("Processing Categories")
            categories = extract_categories_from_response(data)
            
            # Save the extracted categories
            categories_filepath = Path(directories['responses']) / "categories.json"
            save_json(categories, categories_filepath)
            
            # Create summary
            stats = {
                "Categories Found": len(categories),
                "Raw Data Size": f"{len(str(data))} chars",
                "Output File": "categories.json"
            }
            
            console.print(create_summary_table(stats))
            print_success("Category extraction completed", f"Found {len(categories)} categories")
            
            return str(categories_filepath)

        except Exception as e:
            print_error("Scraping failed", f"Error: {str(e)}")
            return None

if __name__ == "__main__":
    asyncio.run(scrape_swiggy_categories())
