#!/usr/bin/env python3
"""
Step 5: Image Downloader
Downloads product images from Swiggy media assets and updates product data files.
Makes the script resumable by tracking images_fetched status.
"""

import asyncio
import sys
import os
import json
import aiohttp
import aiofiles
from pathlib import Path
from typing import Dict, Any, List, Optional
from PIL import Image
import io

from rich.console import Console
from rich.progress import Progress, TaskID, BarColumn, TextColumn, TimeElapsedColumn, TimeRemainingColumn
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

# Add the current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from utils.common import (
    load_config, 
    save_json, 
    ensure_directory
)


class ImageDownloader:
    """Handles downloading and validation of product images."""
    
    def __init__(self, console: Console):
        config = load_config()
        self.base_url = config['api']['media_assets_base_url']
        self.session = None
        self.downloaded_count = 0
        self.failed_count = 0
        self.skipped_count = 0
        self.console = console
        
    async def __aenter__(self):
        """Async context manager entry."""
        connector = aiohttp.TCPConnector(limit=50, limit_per_host=10)
        timeout = aiohttp.ClientTimeout(total=30, connect=10)
        self.session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
            headers={
                'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1'
            }
        )
        return self
        
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        if self.session:
            await self.session.close()
    
    def get_image_extension(self, image_path: str) -> str:
        """
        Determine the file extension for an image.
        If no extension present, default to .png
        """
        if '.' in image_path and image_path.split('.')[-1].lower() in ['jpg', 'jpeg', 'png', 'webp', 'gif']:
            return f".{image_path.split('.')[-1].lower()}"
        return '.png'
    
    def get_filename_from_path(self, image_path: str) -> str:
        """
        Generate a safe filename from image path.
        Always extracts just the filename without any directory structure.
        """
        # For paths like "NI_CATALOG/IMAGES/CIW/2025/7/3/eec94ec0-c890-4702-994a-c809c9f3234b_62203_1.png"
        # Extract just the filename part (last segment after '/')
        if '/' in image_path:
            filename = image_path.split('/')[-1]
        else:
            # For simple hash-like paths
            filename = image_path
        
        # Add extension if not present
        extension = self.get_image_extension(filename)
        if not filename.lower().endswith(('.jpg', '.jpeg', '.png', '.webp', '.gif')):
            filename += extension
            
        return filename
    
    def validate_image(self, image_data: bytes) -> bool:
        """
        Validate that the downloaded data is a valid image.
        """
        try:
            # Try to open the image with PIL
            img = Image.open(io.BytesIO(image_data))
            img.verify()  # Verify the image integrity
            return True
        except Exception:
            return False
    
    async def download_image(self, image_path: str, save_path: Path) -> bool:
        """
        Download a single image and validate it.
        Returns True if successful, False otherwise.
        """
        if save_path.exists():
            self.skipped_count += 1
            return True
        
        # Construct the full URL
        url = f"{self.base_url}{image_path}"
        
        try:
            async with self.session.get(url) as response:
                if response.status == 200:
                    image_data = await response.read()
                    
                    # Validate the image
                    if not self.validate_image(image_data):
                        self.failed_count += 1
                        return False
                    
                    # Save the image
                    async with aiofiles.open(save_path, 'wb') as f:
                        await f.write(image_data)
                    
                    self.downloaded_count += 1
                    return True
                else:
                    self.failed_count += 1
                    return False
                    
        except Exception:
            self.failed_count += 1
            return False
    
    async def download_product_images(self, product_data: Dict[str, Any], product_dir: Path, progress: Progress, task_id: TaskID) -> Dict[str, Any]:
        """
        Download all images for a product and update the data.
        Returns updated product data with local image paths.
        """
        product_id = product_data.get('product_id')
        images = product_data.get('images', [])
        
        if not images:
            return product_data
        
        # Create images directory
        images_dir = product_dir / "images"
        ensure_directory(images_dir)
        
        # Download each image
        downloaded_images = []
        successful_downloads = 0
        
        for i, image_path in enumerate(images):
            if not image_path:  # Skip empty/null image paths
                continue
                
            filename = self.get_filename_from_path(image_path)
            save_path = images_dir / filename
            
            success = await self.download_image(image_path, save_path)
            if success:
                downloaded_images.append(filename)
                successful_downloads += 1
            
            # Update progress
            progress.update(task_id, advance=1)
        
        # Update product data with local image paths
        updated_data = product_data.copy()
        updated_data['images'] = downloaded_images
        updated_data['images_fetched'] = True
        updated_data['images_download_stats'] = {
            'total_images': len(images),
            'downloaded_images': successful_downloads,
            'failed_images': len(images) - successful_downloads
        }
        
        return updated_data


def load_product_data(product_file: Path) -> Optional[Dict[str, Any]]:
    """Load product data from JSON file."""
    try:
        with open(product_file, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception as e:
        print(f"❌ Error loading product data from {product_file}: {e}")
        return None


async def process_single_product(product_dir: Path, downloader: ImageDownloader, progress: Progress, task_id: TaskID, console: Console) -> bool:
    """
    Process a single product directory to download images.
    Returns True if processing was successful.
    """
    product_id = product_dir.name
    data_file = product_dir / "data.json"
    
    if not data_file.exists():
        console.log(f"[yellow]⚠️ No data.json found for product {product_id}[/yellow]")
        return False
    
    # Load product data
    product_data = load_product_data(data_file)
    if not product_data:
        return False
    
    # Check if images already fetched (resumable)
    if product_data.get('images_fetched', False):
        downloader.skipped_count += len(product_data.get('images', []))
        progress.update(task_id, advance=len(product_data.get('images', [])))
        return True
    
    # Download images and update data
    updated_data = await downloader.download_product_images(product_data, product_dir, progress, task_id)
    
    # Save updated data
    save_json(updated_data, data_file)
    
    return True


async def process_all_products(products_dir: Path, max_concurrent: int = 5) -> Dict[str, int]:
    """
    Process all products to download images with concurrency control.
    """
    console = Console()
    
    if not products_dir.exists():
        console.print(f"[red]❌ Products directory not found: {products_dir}[/red]")
        return {}
    
    # Get all product directories
    product_dirs = [d for d in products_dir.iterdir() if d.is_dir() and (d / "data.json").exists()]
    total_products = len(product_dirs)
    
    if total_products == 0:
        console.print("[red]❌ No products found with data.json files[/red]")
        return {}
    
    console.print(f"[green]📁 Found {total_products} products to process[/green]")
    
    # Calculate total images to download
    total_images = 0
    for product_dir in product_dirs:
        data_file = product_dir / "data.json"
        product_data = load_product_data(data_file)
        if product_data and not product_data.get('images_fetched', False):
            total_images += len(product_data.get('images', []))
    
    console.print(f"[cyan]🖼️ Total images to download: {total_images}[/cyan]")
    
    # Process products with concurrency control and progress bar
    async with ImageDownloader(console) as downloader:
        with Progress(
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TimeElapsedColumn(),
            TimeRemainingColumn(),
            console=console
        ) as progress:
            
            # Create progress task
            task_id = progress.add_task("Downloading images...", total=total_images)
            
            semaphore = asyncio.Semaphore(max_concurrent)
            
            async def process_with_semaphore(product_dir):
                async with semaphore:
                    return await process_single_product(product_dir, downloader, progress, task_id, console)
            
            # Process all products
            results = await asyncio.gather(
                *[process_with_semaphore(product_dir) for product_dir in product_dirs],
                return_exceptions=True
            )
            
            # Calculate statistics
            successful_products = sum(1 for result in results if result is True)
            failed_products = total_products - successful_products
            
            stats = {
                'total_products': total_products,
                'successful_products': successful_products,
                'failed_products': failed_products,
                'total_images_downloaded': downloader.downloaded_count,
                'total_images_failed': downloader.failed_count,
                'total_images_skipped': downloader.skipped_count
            }
            
            return stats


def main():
    """Main function to download images for all products."""
    console = Console()
    
    console.print(Panel.fit("🚀 Starting Image Download (Step 5)", style="bold blue"))
    
    try:
        # Load configuration
        config = load_config()
        responses_dir = Path(config['output']['base_directory'])
        products_dir = responses_dir / "products"
        
        if not products_dir.exists():
            console.print(f"[red]❌ Products directory not found: {products_dir}[/red]")
            console.print("[yellow]   Please run step4_extract_products.py first.[/yellow]")
            return 1
        
        # Start processing
        console.print(f"[green]📁 Processing products from: {products_dir}[/green]")
        stats = asyncio.run(process_all_products(products_dir, max_concurrent=5))
        
        if not stats:
            return 1
        
        # Create final summary table
        table = Table(title="📊 Final Statistics", show_header=True, header_style="bold magenta")
        table.add_column("Metric", style="cyan", no_wrap=True)
        table.add_column("Value", style="white")
        
        table.add_row("Products processed", f"{stats['successful_products']}/{stats['total_products']}")
        table.add_row("Images downloaded", f"{stats['total_images_downloaded']:,}")
        table.add_row("Images failed", f"{stats['total_images_failed']:,}")
        table.add_row("Images skipped", f"{stats['total_images_skipped']:,}")
        
        if stats['failed_products'] > 0:
            table.add_row("Failed products", f"[red]{stats['failed_products']}[/red]")
        
        console.print("\n")
        console.print(table)
        console.print(Panel.fit("🎉 Image download completed!", style="bold green"))
        
        return 0
        
    except Exception as e:
        console.print(f"[red]❌ Unexpected error: {e}[/red]")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
