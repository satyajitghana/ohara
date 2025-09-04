#!/usr/bin/env python3
"""
Step 2: Swiggy Category Scraper
Scrapes category listing pages using the data from step1_scrape_home_v2.py.
Handles pagination and saves all category data.
"""

import asyncio
import sys
from pathlib import Path
from typing import Dict, Any, List, Set

# Add the current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

from playwright.async_api import async_playwright

from utils.common import (
    load_config, 
    load_json, 
    save_json, 
    convert_deeplink_to_web_url, 
    create_safe_filename,
    ensure_directory,
    print_directory_structure_summary
)
from utils.scraper import (
    setup_api_interceptors,
    navigate_with_retry,
    perform_smart_scroll,
    trigger_mouse_interaction,
    process_pagination_responses,
    cleanup_partial_data,
    print_scraping_summary,
    print_final_summary
)


async def scrape_category_attempt(
    browser, 
    device_config: dict, 
    category: dict, 
    responses_dir: Path, 
    index: int, 
    safe_filename: str
) -> str:
    """Single attempt to scrape a category."""
    category_name = category['category_name']
    config = load_config()
    
    context = await browser.new_context(**device_config)
    print(f"[{index}] 📱 Context created for {category_name}")
    
    try:
        # Create page using the context
        page = await context.new_page()
        print(f"[{index}] 📱 Using Pixel 5 device configuration for {category_name}")
        
        # Set up API request and response interception
        api_responses = []
        api_requests = []
        await setup_api_interceptors(page, api_responses, api_requests, index)
        
        # Convert deeplink to web URL
        web_url = convert_deeplink_to_web_url(category['deeplink'])
        print(f"[{index}] URL: {web_url}")
        
        # Create category-specific directory under categories/
        config = load_config()
        categories_subdir = config['output']['categories_subdirectory']
        categories_base_dir = responses_dir / categories_subdir
        ensure_directory(categories_base_dir)
        category_dir = categories_base_dir / safe_filename
        ensure_directory(category_dir)
        
        # Navigate with retry mechanism for handling rate limits
        initial_state = await navigate_with_retry(page, web_url, index)
        
        # Save HTML content (from the last successful attempt)
        html_content = await page.content()
        html_file = category_dir / f"{safe_filename}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[{index}] 💾 Saved HTML to {html_file}")
        
        # Final check if we failed to get valid data after all retries
        if not initial_state:
            # Debug: check what script tags are actually present
            print(f"[{index}] 🐛 Debugging: Checking for script tags in HTML...")
            from bs4 import BeautifulSoup
            soup = BeautifulSoup(html_content, 'html.parser')
            scripts = soup.find_all('script')
            print(f"[{index}] 🐛 Found {len(scripts)} script tags")
            
            # Look for any script containing "INITIAL_STATE"
            initial_state_scripts = [s for s in scripts if s.string and 'INITIAL_STATE' in s.string]
            print(f"[{index}] 🐛 Found {len(initial_state_scripts)} scripts containing 'INITIAL_STATE'")
            
            if initial_state_scripts:
                print(f"[{index}] 🐛 First INITIAL_STATE script preview: {initial_state_scripts[0].string[:200]}...")
            
            max_retries = config['scraping']['max_retries']
            print(f"[{index}] ❌ CRITICAL: Could not get valid data after {max_retries} retries. Aborting scrape for this category.")
            return f"Failed - No valid data after {max_retries} retries"
        
        initial_state_file = category_dir / f"{safe_filename}_initial_state.json"
        save_json(initial_state, initial_state_file)
        print(f"[{index}] 💾 Saved initial state to {initial_state_file}")
        
        category_data = initial_state.get('instamart', {}).get('categoryData', {})
        saved_pages: Set[int] = set()  # Track which pages we've already saved
        
        if category_data:
            # Wrap data to match the structure of paginated API calls for consistency
            page_0_data = {"data": category_data}
            category_data_file = category_dir / f"{safe_filename}_page_0.json"
            save_json(page_0_data, category_data_file)
            print(f"[{index}] 💾 Saved page 0 data to {category_data_file}")
            saved_pages.add(0)  # Mark page 0 as saved
        
        # Now scroll to trigger pagination
        print(f"[{index}] 🔄 Starting pagination by scrolling...")
        
        page_count = 1
        has_more = True
        max_scroll_loops = config['scraping']['max_scroll_loops']
        api_wait_seconds = config['scraping']['api_wait_seconds']
        final_wait_seconds = config['scraping']['final_wait_seconds']
        
        while has_more and page_count <= max_scroll_loops:
            print(f"[{index}] ⬇️ Scroll loop iteration {page_count}...")
            
            post_filter_responses_before = [
                r for r in api_responses 
                if "/api/instamart/category-listing/filter" in r.get('url', '') and r.get('method') == 'POST'
            ]
            responses_before_scroll = len(post_filter_responses_before)

            try:
                # Perform smart scrolling
                await perform_smart_scroll(page, index)
                
                # Add mouse interaction to trigger fetch calls
                await trigger_mouse_interaction(page, index)
                
                print(f"[{index}] ⏳ Waiting for API responses to be captured...")
                await asyncio.sleep(api_wait_seconds)

                # Process pagination responses
                has_more, api_error = await process_pagination_responses(
                    api_responses, 
                    responses_before_scroll,
                    category_dir,
                    safe_filename,
                    saved_pages,
                    page_count,
                    index
                )
                
                if api_error:
                    return "Failed - API_ERROR - Session corrupted"
                    
            except Exception as e:
                print(f"[{index}] ⚠️ Error during scroll/pagination loop: {e}")
                has_more = False

            if not has_more:
                print(f"[{index}] ✅ Reached last page for {category_name}.")
                break
            
            page_count += 1
            await asyncio.sleep(final_wait_seconds)
        
        # Save API requests and responses
        if api_requests:
            api_requests_file = category_dir / f"{safe_filename}_api_requests.json"
            save_json(api_requests, api_requests_file)
            print(f"[{index}] 💾 Saved {len(api_requests)} API requests to {api_requests_file}")
        
        if api_responses:
            api_responses_file = category_dir / f"{safe_filename}_api_responses.json"
            save_json(api_responses, api_responses_file)
            print(f"[{index}] 💾 Saved {len(api_responses)} API responses to {api_responses_file}")
        
        # Print summary
        print_scraping_summary(category_name, api_requests, api_responses, saved_pages, index)
        
        return "Success"
        
    except Exception as e:
        print(f"[{index}] ❌ Error scraping {category_name}: {e}")
        return f"Failed - {str(e)}"
    finally:
        await context.close()
        print(f"[{index}] 🔒 Context closed for {category_name}.")


async def scrape_category_with_pagination(
    browser, 
    device_config: dict, 
    category: dict, 
    responses_dir: Path, 
    index: int
) -> str:
    """Scrape a single category, creating its own browser context, and capture paginated API calls."""
    category_name = category['category_name']
    safe_filename = create_safe_filename(category_name)
    config = load_config()
    
    print(f"[{index}] 🌐 Starting scrape for: {category_name}")
    
    # Retry mechanism for entire category when API errors occur
    max_category_retries = config['scraping']['max_category_retries']
    category_retry_delay = config['scraping']['category_retry_delay_seconds']
    category_retry_count = 0
    
    while category_retry_count < max_category_retries:
        if category_retry_count > 0:
            print(f"[{index}] 🔄 Category retry {category_retry_count}/{max_category_retries} for {category_name} due to API errors")
            await asyncio.sleep(category_retry_delay)  # Wait longer between category retries
            
            # Clean up any partial data from previous failed attempt
            config = load_config()
            categories_subdir = config['output']['categories_subdirectory']
            categories_base_dir = responses_dir / categories_subdir
            category_dir = categories_base_dir / safe_filename
            cleanup_partial_data(category_dir, index)
        
        try:
            result = await scrape_category_attempt(browser, device_config, category, responses_dir, index, safe_filename)
            if result == "Success":
                return result
            elif "API_ERROR" in result:
                print(f"[{index}] ⚠️ API session corrupted, will retry entire category with fresh start...")
                category_retry_count += 1
                continue
            else:
                return result  # Other types of failures, don't retry
        except Exception as e:
            print(f"[{index}] ❌ Exception in category attempt: {e}")
            category_retry_count += 1
            continue
    
    return f"Failed - Max category retries ({max_category_retries}) exceeded"


async def scrape_all_categories(categories: List[Dict[str, Any]], responses_dir: Path) -> None:
    """Scrape all categories in parallel batches."""
    config = load_config()
    max_concurrent = config['scraping']['max_concurrent_categories']
    batch_delay = config['scraping']['batch_delay_seconds']
    
    async with async_playwright() as p:
        device_config = p.devices['Pixel 5']
        browser = await p.chromium.launch(headless=True)
        
        all_results = []
        indexed_categories = list(enumerate(categories, 1))
        
        category_chunks = [
            indexed_categories[i:i + max_concurrent] 
            for i in range(0, len(indexed_categories), max_concurrent)
        ]
        
        for i, chunk in enumerate(category_chunks):
            print(f"\n🚀 Processing batch {i + 1}/{len(category_chunks)} with {len(chunk)} categories in parallel...")
            
            tasks = [
                scrape_category_with_pagination(browser, device_config, category, responses_dir, index)
                for index, category in chunk
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(batch_results)
            
            if i < len(category_chunks) - 1:
                print(f"✅ Batch {i + 1} complete. Waiting {batch_delay} seconds before next batch...")
                await asyncio.sleep(batch_delay)
        
        await browser.close()
        
        # Print final summary
        print_final_summary(all_results, len(categories))


def load_categories_from_step1() -> List[Dict[str, Any]]:
    """Load categories from step1 output."""
    config = load_config()
    output_config = config['output']
    
    responses_dir = Path(output_config['base_directory'])
    categories_file = responses_dir / output_config['home_api_filename']
    
    if not categories_file.exists():
        print(f"❌ Categories file not found: {categories_file}")
        print(f"   Please run step1_scrape_home_v2.py first")
        return []
    
    data = load_json(categories_file)
    if not data:
        print(f"❌ Could not load categories from {categories_file}")
        return []
    
    categories = data.get('categories', [])
    print(f"📋 Loaded {len(categories)} categories from {categories_file}")
    return categories


def main():
    """Main function to scrape all categories."""
    print("🚀 Starting Swiggy Category Scraper (Step 2)...")
    
    try:
        # Load categories from step1
        categories = load_categories_from_step1()
        
        if not categories:
            print("❌ No categories found. Please run step1_scrape_home_v2.py first.")
            return 1
        
        # Create responses directory
        config = load_config()
        responses_dir = Path(config['output']['base_directory'])
        ensure_directory(responses_dir)
        print(f"📁 Using output directory: {responses_dir}")
        
        # Start scraping
        print(f"\n🚀 Starting category scraping for {len(categories)} categories...")
        asyncio.run(scrape_all_categories(categories, responses_dir))
        
        print(f"\n🎉 Category scraping completed!")
        print(f"📁 Results saved in: {responses_dir}")
        
        # Show directory structure summary
        print_directory_structure_summary(responses_dir)
        
        return 0
        
    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
