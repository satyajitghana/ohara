import httpx
import json
import asyncio
import os
from pathlib import Path
from rich.progress import Progress, BarColumn, TextColumn, TimeRemainingColumn
from rich.console import Console

# Hardcoded list of categories to process
CATEGORIES_TO_PROCESS = [
    "Biscuits_and_Cakes.json",
    "Cereals_and_Breakfast.json",
    "Chips_and_Namkeens.json",
    "Chocolates.json",
    "Cold_Drinks_and_Juices.json",
    "Dairy,_Bread_and_Eggs.json",
    "Dry_Fruits_and_Seeds_Mix.json",
    "Frozen_Food.json",
    "Ice_Creams_and_Frozen_Desserts.json",
    "Meat_and_Seafood.json",
    "Masalas.json",
    "Noodles,_Pasta,_Vermicelli.json",
    "Oils_and_Ghee.json",
    "Protein_and_Supplements.json",
    "Sauces_and_Spreads.json",
    "Sweets.json",
    "Tea,_Coffee_and_Milk_drinks.json"
]

async def download_image(client, image_id, download_path, semaphore):
    """
    Downloads an image from Swiggy's CDN.
    """
    async with semaphore:
        base_url = "https://instamart-media-assets.swiggy.com/swiggy/image/upload/"
        image_url = f"{base_url}{image_id}"
        
        try:
            response = await client.get(image_url, timeout=20.0)
            response.raise_for_status()
            
            with open(download_path, 'wb') as f:
                f.write(response.content)
            return True
        except httpx.HTTPStatusError as e:
            # This will be visible below the progress bar
            Console().print(f"  [bold red]❌ HTTP ERROR[/bold red] downloading {image_url}: {e.response.status_code}")
            return False
        except Exception as e:
            Console().print(f"  [bold red]❌ Unexpected error[/bold red] downloading {image_url}: {type(e).__name__} - {e}")
            return False

def clean_image_id(image_id):
    """
    Cleans the image ID to be used as a filename.
    e.g., NI_CATALOG/IMAGES/CIW/2025/4/10/xyz.png -> xyz.png
    e.g., 5b0f010e1c9b2ebce6a965512a896ba6 -> 5b0f010e1c9b2ebce6a965512a896ba6.png
    """
    filename = Path(image_id).name
    if not Path(filename).suffix:
        filename += ".png"
    return filename


async def process_product(product_data, output_dir, client, semaphore, progress, task_id):
    """
    Processes a single product, saves its data, and downloads its images.
    """
    try:
        product_id = product_data.get("product_id")
        if not product_id:
            # Using console.log to avoid interfering with the progress bar
            Console().log("[yellow]⚠️ Skipping product with no product_id.[/yellow]")
            return

        product_dir = output_dir / product_id
        product_dir.mkdir(exist_ok=True)

        # Save all product data (including variations)
        with open(product_dir / "data.json", 'w', encoding='utf-8') as f:
            json.dump(product_data, f, indent=2, ensure_ascii=False)

        for variation in product_data.get("variations", []):
            variation_id = variation.get("id")
            if not variation_id:
                Console().log(f"[yellow]⚠️ Skipping variation with no id for product {product_id}.[/yellow]")
                continue
            
            variation_dir = product_dir / variation_id
            variation_dir.mkdir(exist_ok=True)
            
            # Save variation-specific data
            with open(variation_dir / "data.json", 'w', encoding='utf-8') as f:
                json.dump(variation, f, indent=2, ensure_ascii=False)
                
            images_dir = variation_dir / "images"
            images_dir.mkdir(exist_ok=True)
            
            image_ids = variation.get("images", [])
            download_tasks = []
            for image_id in image_ids:
                cleaned_filename = clean_image_id(image_id)
                download_path = images_dir / cleaned_filename
                if not download_path.exists(): # Avoid re-downloading
                    download_tasks.append(download_image(client, image_id, download_path, semaphore))
            
            if download_tasks:
                await asyncio.gather(*download_tasks)
    finally:
        progress.update(task_id, advance=1)


async def process_category_file(filepath, output_dir, client, semaphore, progress, task_id):
    """
    Reads a category JSON file and processes each product within it.
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
            products = []
            if isinstance(data, list):
                products = data
            elif isinstance(data, dict):
                # This handles the nested structure seen in some files
                products = data.get("data", {}).get("widgets", [{}])[0].get("data", {}).get("products", [])
            
            if not products:
                Console().log(f"[yellow]  ⚠️  No products found in {filepath.name}[/yellow]")
                return

            tasks = [process_product(product, output_dir, client, semaphore, progress, task_id) for product in products]
            await asyncio.gather(*tasks)

        except json.JSONDecodeError:
            Console().print(f"[bold red]  ❌ Error decoding JSON from {filepath.name}[/bold red]")
        except (IndexError, KeyError) as e:
            Console().print(f"[bold red]  ❌ Could not find products in {filepath.name}, structure might have changed. Error: {e}[/bold red]")


async def main():
    """
    Main function to orchestrate the processing of product listings.
    """
    console = Console()
    listings_dir = Path("responses/listings")
    output_dir = Path("scraped_data")
    output_dir.mkdir(exist_ok=True)

    console.print("[bold green]🚀 Starting data processing and image download...[/bold green]")
    
    semaphore = asyncio.Semaphore(10) # Concurrency limit for downloads

    # Define the progress bar columns
    progress_columns = [
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
        TextColumn("({task.completed} of {task.total})"),
        TimeRemainingColumn(),
    ]

    with Progress(*progress_columns, console=console) as progress:
        async with httpx.AsyncClient() as client:
            for category_file in CATEGORIES_TO_PROCESS:
                filepath = listings_dir / category_file
                if filepath.exists():
                    console.log(f"Processing [bold cyan]{filepath.name}[/bold cyan]...")
                    
                    # First, read the file to count products for the progress bar
                    with open(filepath, 'r', encoding='utf-8') as f:
                        try:
                            data = json.load(f)
                            products = []
                            if isinstance(data, list):
                                products = data
                            elif isinstance(data, dict):
                                products = data.get("data", {}).get("widgets", [{}])[0].get("data", {}).get("products", [])
                            
                            if products:
                                category_name = Path(category_file).stem.replace('_', ' ')
                                task_id = progress.add_task(f"  [green]{category_name}[/green]", total=len(products))
                                await process_category_file(filepath, output_dir, client, semaphore, progress, task_id)
                            else:
                                console.log(f"[yellow]  ⚠️  No products found in {filepath.name}[/yellow]")

                        except json.JSONDecodeError:
                            console.print(f"[bold red]  ❌ Error decoding JSON from {filepath.name}[/bold red]")

                else:
                    console.log(f"[yellow]⚠️ File not found: {filepath.name}[/yellow]")
        
    console.print("[bold green]✅ All categories processed.[/bold green]")

if __name__ == "__main__":
    asyncio.run(main())
