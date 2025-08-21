import asyncio
import json
from pathlib import Path
from utils.config import get_api_config, get_directories_config, get_categories_to_process
from utils.http_client import create_http_client, download_image
from utils.file_operations import save_json, load_json, clean_image_id
from utils.data_processing import extract_products_from_data
from utils.console_utils import (
    get_console, get_progress_bar, print_success, print_warning, log_message,
    create_header, print_banner, create_summary_table, print_info, print_error
)


async def process_category_metadata(category_metadata, output_dir, client, semaphore):
    """
    Process category metadata and download category images.
    """
    if not category_metadata:
        return
    
    # Create categories directory for storing category images
    categories_dir = output_dir / "swiggy" / "categories"
    categories_dir.mkdir(parents=True, exist_ok=True)
    
    # Create images subdirectory within categories
    images_dir = categories_dir / "images"
    images_dir.mkdir(exist_ok=True)
    
    # Process and clean category metadata
    cleaned_categories = []
    cleaned_filters = []
    download_tasks = []
    
    # Process main categories
    for category in category_metadata.get("categories", []):
        image_id = category.get("image_id")
        cleaned_filename = None
        
        if image_id:
            cleaned_filename = clean_image_id(image_id)
            download_path = images_dir / cleaned_filename
            if not download_path.exists():  # Avoid re-downloading
                download_tasks.append(download_image(client, image_id, str(download_path), semaphore))
        
        # Create cleaned category data
        cleaned_category = {
            "id": category.get("id"),
            "display_name": category.get("display_name"),
            "product_count": category.get("product_count"),
            "image_filename": cleaned_filename,
            "age_consent_required": category.get("age_consent_required", False)
        }
        cleaned_categories.append(cleaned_category)
    
    # Process filters/subcategories
    for filter_item in category_metadata.get("filters", []):
        image_id = filter_item.get("image_id")
        cleaned_filename = None
        
        if image_id:
            cleaned_filename = clean_image_id(image_id)
            download_path = images_dir / cleaned_filename
            if not download_path.exists():  # Avoid re-downloading
                download_tasks.append(download_image(client, image_id, str(download_path), semaphore))
        
        # Create cleaned filter data
        cleaned_filter = {
            "id": filter_item.get("id"),
            "name": filter_item.get("name"),
            "image_filename": cleaned_filename,
            "type": filter_item.get("type"),
            "product_count": filter_item.get("product_count")
        }
        cleaned_filters.append(cleaned_filter)
    
    if download_tasks:
        await asyncio.gather(*download_tasks)
    
    # Create cleaned metadata structure
    cleaned_metadata = {
        "categories": cleaned_categories,
        "selected_category": category_metadata.get("selected_category"),
        "filters": cleaned_filters,
        "category_name": category_metadata.get('category_name', 'unknown')
    }
    
    # Save cleaned category metadata to categories directory
    metadata_path = categories_dir / f"{category_metadata.get('category_name', 'unknown')}_metadata.json"
    save_json(cleaned_metadata, str(metadata_path))


async def process_product(product_data, output_dir, client, semaphore, progress, task_id):
    """
    Processes a single product, saves its data, and downloads its images.
    Uses brand_id/variation_id folder structure in listings directory.
    """
    try:
        product_id = product_data.get("product_id")
        brand_id = product_data.get("brand_id")
        brand_name = product_data.get("brand")
        
        if not product_id or not brand_id:
            log_message("[yellow]⚠️ Skipping product with missing product_id or brand_id.[/yellow]")
            return

        # Create brand directory in listings
        listings_dir = output_dir / "swiggy" / "listings"
        listings_dir.mkdir(parents=True, exist_ok=True)
        brand_dir = listings_dir / brand_id
        brand_dir.mkdir(exist_ok=True)
        
        # Save/update brand information
        brand_info_path = brand_dir / "brand_info.json"
        brand_info = {
            "brand_id": brand_id,
            "brand_name": brand_name,
            "last_updated": None  # Could add timestamp if needed
        }
        save_json(brand_info, str(brand_info_path))
        
        # Load or create products list for this brand
        products_list_path = brand_dir / "products_list.json"
        try:
            products_list = load_json(products_list_path)
        except (FileNotFoundError, json.JSONDecodeError):
            products_list = {"product_ids": [], "products_info": {}, "variations": {}}
        
        # Add product to the list if not already present
        if product_id not in products_list["product_ids"]:
            products_list["product_ids"].append(product_id)
        
        # Initialize product info if not exists
        if product_id not in products_list["products_info"]:
            products_list["products_info"][product_id] = {
                "display_name": product_data.get("display_name"),
                "brand": brand_name,
                "brand_id": brand_id,
                "product_id": product_id,
                "variation_ids": [],
                "variation_count": 0
            }
        
        # Track all variations for this product
        for variation in product_data.get("variations", []):
            variation_id = variation.get("id")
            if variation_id and variation_id not in products_list["products_info"][product_id]["variation_ids"]:
                products_list["products_info"][product_id]["variation_ids"].append(variation_id)
                
                # Store variation details
                products_list["variations"][variation_id] = {
                    "variation_id": variation_id,
                    "product_id": product_id,
                    "display_name": variation.get("display_name"),
                    "quantity": variation.get("quantity"),
                    "sku_quantity_with_combo": variation.get("sku_quantity_with_combo"),
                    "price": variation.get("price", {}).get("offer_price"),
                    "mrp": variation.get("price", {}).get("mrp")
                }
        
        # Update variation count
        products_list["products_info"][product_id]["variation_count"] = len(products_list["products_info"][product_id]["variation_ids"])
        
        # Save updated products list
        save_json(products_list, str(products_list_path))

        # Process each variation
        for variation in product_data.get("variations", []):
            variation_id = variation.get("id")
            if not variation_id:
                log_message(f"[yellow]⚠️ Skipping variation with no id for product {product_id}.[/yellow]")
                continue
            
            variation_dir = brand_dir / variation_id
            variation_dir.mkdir(exist_ok=True)
            
            # Save variation data with parent product info for context
            variation_data = {
                "variation": variation,
                "parent_product": {
                    "product_id": product_id,
                    "display_name": product_data.get("display_name"),
                    "brand": brand_name,
                    "brand_id": brand_id
                }
            }
            save_json(variation_data, str(variation_dir / "data.json"))
                
            images_dir = variation_dir / "images"
            images_dir.mkdir(exist_ok=True)
            
            image_ids = variation.get("images", [])
            download_tasks = []
            for image_id in image_ids:
                cleaned_filename = clean_image_id(image_id)
                download_path = images_dir / cleaned_filename
                if not download_path.exists():  # Avoid re-downloading
                    download_tasks.append(download_image(client, image_id, str(download_path), semaphore))
            
            if download_tasks:
                await asyncio.gather(*download_tasks)
    finally:
        progress.update(task_id, advance=1)


async def process_category_file(filepath, output_dir, client, semaphore, progress, task_id):
    """
    Reads a category JSON file and processes each product within it.
    Also processes category metadata if available.
    """
    try:
        data = load_json(filepath)
        products = extract_products_from_data(data)
        
        if not products:
            log_message(f"No products found in {filepath.name}", "warning")
            return

        # Check for corresponding metadata file
        category_name = filepath.stem
        metadata_filepath = filepath.parent / f"{category_name}_metadata.json"
        if metadata_filepath.exists():
            try:
                category_metadata = load_json(metadata_filepath)
                # Add category name to metadata for proper file naming
                category_metadata['category_name'] = category_name
                await process_category_metadata(category_metadata, output_dir, client, semaphore)
                log_message(f"Processed category metadata for {category_name}", "info")
            except Exception as e:
                log_message(f"Error processing category metadata for {category_name}: {str(e)}", "warning")

        tasks = [process_product(product, output_dir, client, semaphore, progress, task_id) for product in products]
        await asyncio.gather(*tasks)

    except Exception as e:
        log_message(f"Error processing {filepath.name}: {str(e)}", "error")


async def process_main_categories(output_dir, client, semaphore):
    """
    Process main categories file and download category images.
    """
    try:
        directories = get_directories_config()
        categories_filepath = Path(directories['responses']) / "categories.json"
        
        if categories_filepath.exists():
            categories = load_json(categories_filepath)
            
            # Create categories directory for storing category images
            categories_dir = output_dir / "swiggy" / "categories"
            categories_dir.mkdir(parents=True, exist_ok=True)
            
            # Create images subdirectory within categories
            images_dir = categories_dir / "images"
            images_dir.mkdir(exist_ok=True)
            
            # Process and clean categories data
            cleaned_categories = []
            download_tasks = []
            
            for category in categories:
                image_id = category.get("imageId")
                cleaned_filename = None
                
                if image_id:
                    cleaned_filename = clean_image_id(image_id)
                    download_path = images_dir / cleaned_filename
                    if not download_path.exists():  # Avoid re-downloading
                        download_tasks.append(download_image(client, image_id, str(download_path), semaphore))
                
                # Create cleaned category data with only essential fields
                cleaned_category = {
                    "description": category.get("description"),
                    "image_filename": cleaned_filename,
                    "taxonomyType": category.get("link_params", {}).get("taxonomyType")
                }
                cleaned_categories.append(cleaned_category)
            
            if download_tasks:
                await asyncio.gather(*download_tasks)
                log_message(f"Downloaded {len(download_tasks)} main category images", "info")
            
            # Save the cleaned categories data to the categories directory
            super_categories_path = categories_dir / "super_categories.json"
            save_json(cleaned_categories, str(super_categories_path))
            
    except Exception as e:
        log_message(f"Error processing main categories: {str(e)}", "warning")


async def main():
    """
    Main function to orchestrate the processing of product listings.
    """
    console = get_console()
    
    # Print beautiful header
    header = create_header(
        "🎯 Swiggy Data Processor & Image Downloader", 
        "Processing product data and downloading images"
    )
    console.print(header)
    
    directories = get_directories_config()
    api_config = get_api_config()
    categories_to_process = get_categories_to_process()
    
    listings_dir = Path(directories['listings'])
    output_dir = Path(directories['scraped_data'])
    output_dir.mkdir(parents=True, exist_ok=True)

    print_info("Initialization complete", f"Processing {len(categories_to_process)} categories")
    
    # Concurrency limit for downloads
    concurrency_limit = api_config.get('concurrency_limit', 10)
    semaphore = asyncio.Semaphore(concurrency_limit)
    
    total_products = 0
    total_images = 0
    processed_categories = 0

    print_banner("Starting Data Processing")

    with get_progress_bar(show_speed=True) as progress:
        overall_task = progress.add_task(
            "[bold green]Processing categories...", 
            total=len(categories_to_process)
        )
        
        async with await create_http_client() as client:
            # Process main categories and download their images first
            log_message("Processing main categories and downloading category images", "info")
            await process_main_categories(output_dir, client, semaphore)
            
            for category_file in categories_to_process:
                filepath = listings_dir / category_file
                if filepath.exists():
                    
                    try:
                        data = load_json(filepath)
                        products = extract_products_from_data(data)
                        
                        if products:
                            category_name = Path(category_file).stem.replace('_', ' ')
                            task_id = progress.add_task(
                                f"[cyan]  └─ {category_name}", 
                                total=len(products)
                            )
                            
                            log_message(f"Processing {category_name}: {len(products)} products", "info")
                            await process_category_file(filepath, output_dir, client, semaphore, progress, task_id)
                            
                            total_products += len(products)
                            processed_categories += 1
                            
                            progress.remove_task(task_id)
                            log_message(f"Completed {category_name}", "success")
                        else:
                            log_message(f"No products in {filepath.name}", "warning")

                    except Exception as e:
                        log_message(f"Error reading {filepath.name}: {str(e)}", "error")

                else:
                    log_message(f"File not found: {filepath.name}", "warning")
                
                progress.update(overall_task, advance=1)
    
    # Final summary
    print_banner("Processing Complete")
    stats = {
        "Categories Processed": processed_categories,
        "Total Products": total_products,
        "Concurrency Limit": concurrency_limit,
        "Output Directory": str(output_dir)
    }
    console.print(create_summary_table(stats))
    print_success("All processing completed successfully")

if __name__ == "__main__":
    asyncio.run(main())
