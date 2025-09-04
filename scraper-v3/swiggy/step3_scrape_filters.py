#!/usr/bin/env python3
"""
Step 3: Swiggy Filter Scraper
Scrapes filter-specific listings for each category using data from step2.
Handles pagination and saves all filter data with the same logic as category scraping.
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
    save_json, 
    build_filter_url,
    create_safe_filename,
    ensure_directory,
    print_directory_structure_summary,
    load_categories_from_output
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


async def scrape_filter_attempt(
    browser, 
    device_config: dict, 
    category_info: dict,
    filter_info: dict, 
    responses_dir: Path, 
    index: int, 
    safe_filter_name: str
) -> str:
    """Single attempt to scrape a filter."""
    category_name = category_info['category_name']
    filter_name = filter_info['name']
    config = load_config()
    
    context = await browser.new_context(**device_config)
    print(f"[{index}] 📱 Context created for {category_name} -> {filter_name}")
    
    try:
        # Create page using the context
        page = await context.new_page()
        print(f"[{index}] 📱 Using Pixel 5 device configuration")
        
        # Set up API request and response interception
        api_responses = []
        api_requests = []
        await setup_api_interceptors(page, api_responses, api_requests, index)
        
        # Build filter URL
        filter_url = build_filter_url(
            category_name=category_name,
            filter_id=filter_info['id'],
            filter_name=filter_info['name'],
            filter_type=filter_info['type']
        )
        print(f"[{index}] URL: {filter_url}")
        
        # Create filter-specific directory structure
        config = load_config()
        categories_subdir = config['output']['categories_subdirectory']
        categories_base_dir = responses_dir / categories_subdir
        category_dir = categories_base_dir / category_info['folder_name']
        filters_dir = category_dir / "filters"
        ensure_directory(filters_dir)
        filter_dir = filters_dir / safe_filter_name
        ensure_directory(filter_dir)
        
        # Navigate with retry mechanism for handling rate limits
        initial_state = await navigate_with_retry(page, filter_url, index)
        
        # Save HTML content (from the last successful attempt)
        html_content = await page.content()
        html_file = filter_dir / f"{safe_filter_name}.html"
        with open(html_file, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"[{index}] 💾 Saved HTML to {html_file}")
        
        # Final check if we failed to get valid data after all retries
        if not initial_state:
            max_retries = config['scraping']['max_retries']
            print(f"[{index}] ❌ CRITICAL: Could not get valid data after {max_retries} retries for filter {filter_name}")
            return f"Failed - No valid data after {max_retries} retries"
        
        initial_state_file = filter_dir / f"{safe_filter_name}_initial_state.json"
        save_json(initial_state, initial_state_file)
        print(f"[{index}] 💾 Saved initial state to {initial_state_file}")
        
        category_data = initial_state.get('instamart', {}).get('categoryData', {})
        saved_pages: Set[int] = set()  # Track which pages we've already saved
        
        if category_data:
            # Wrap data to match the structure of paginated API calls for consistency
            page_0_data = {"data": category_data}
            filter_data_file = filter_dir / f"{safe_filter_name}_page_0.json"
            save_json(page_0_data, filter_data_file)
            print(f"[{index}] 💾 Saved page 0 data to {filter_data_file}")
            saved_pages.add(0)  # Mark page 0 as saved
        
        # Now scroll to trigger pagination
        print(f"[{index}] 🔄 Starting pagination by scrolling for filter {filter_name}...")
        
        page_count = 1
        has_more = True
        max_scroll_loops = config['scraping']['max_scroll_loops']
        api_wait_seconds = config['scraping']['api_wait_seconds']
        final_wait_seconds = config['scraping']['final_wait_seconds']
        
        while has_more and page_count <= max_scroll_loops:
            print(f"[{index}] ⬇️ Scroll loop iteration {page_count} for filter {filter_name}...")
            
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
                    filter_dir,
                    safe_filter_name,
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
                print(f"[{index}] ✅ Reached last page for filter {filter_name}.")
                break
            
            page_count += 1
            await asyncio.sleep(final_wait_seconds)
        
        # Save API requests and responses
        if api_requests:
            api_requests_file = filter_dir / f"{safe_filter_name}_api_requests.json"
            save_json(api_requests, api_requests_file)
            print(f"[{index}] 💾 Saved {len(api_requests)} API requests to {api_requests_file}")
        
        if api_responses:
            api_responses_file = filter_dir / f"{safe_filter_name}_api_responses.json"
            save_json(api_responses, api_responses_file)
            print(f"[{index}] 💾 Saved {len(api_responses)} API responses to {api_responses_file}")
        
        # Print summary
        print_scraping_summary(f"{category_name} -> {filter_name}", api_requests, api_responses, saved_pages, index)
        
        return "Success"
        
    except Exception as e:
        print(f"[{index}] ❌ Error scraping filter {filter_name}: {e}")
        return f"Failed - {str(e)}"
    finally:
        await context.close()
        print(f"[{index}] 🔒 Context closed for {category_name} -> {filter_name}")


async def scrape_filter_with_retry(
    browser, 
    device_config: dict, 
    category_info: dict,
    filter_info: dict, 
    responses_dir: Path, 
    index: int
) -> str:
    """Scrape a single filter with retry logic."""
    category_name = category_info['category_name']
    filter_name = filter_info['name']
    safe_filter_name = create_safe_filename(filter_name)
    config = load_config()
    
    print(f"[{index}] 🌐 Starting filter scrape: {category_name} -> {filter_name}")
    
    # Retry mechanism for entire filter when API errors occur
    max_filter_retries = config['scraping']['max_filter_retries']
    filter_retry_delay = config['scraping']['filter_retry_delay_seconds']
    filter_retry_count = 0
    
    while filter_retry_count < max_filter_retries:
        if filter_retry_count > 0:
            print(f"[{index}] 🔄 Filter retry {filter_retry_count}/{max_filter_retries} for {filter_name} due to API errors")
            await asyncio.sleep(filter_retry_delay)
            
            # Clean up any partial data from previous failed attempt
            config = load_config()
            categories_subdir = config['output']['categories_subdirectory']
            categories_base_dir = responses_dir / categories_subdir
            category_dir = categories_base_dir / category_info['folder_name']
            filters_dir = category_dir / "filters"
            filter_dir = filters_dir / safe_filter_name
            cleanup_partial_data(filter_dir, index)
        
        try:
            result = await scrape_filter_attempt(
                browser, device_config, category_info, filter_info, responses_dir, index, safe_filter_name
            )
            if result == "Success":
                return result
            elif "API_ERROR" in result:
                print(f"[{index}] ⚠️ API session corrupted, will retry filter with fresh start...")
                filter_retry_count += 1
                continue
            else:
                return result  # Other types of failures, don't retry
        except Exception as e:
            print(f"[{index}] ❌ Exception in filter attempt: {e}")
            filter_retry_count += 1
            continue
    
    return f"Failed - Max filter retries ({max_filter_retries}) exceeded"


async def scrape_category_filters(
    browser,
    device_config: dict,
    category_info: dict,
    responses_dir: Path,
    category_index: int
) -> List[str]:
    """Scrape all filters for a single category."""
    category_name = category_info['category_name']
    filters = category_info['filters']
    config = load_config()
    
    if not filters:
        print(f"[Cat {category_index}] ⚠️ No filters found for category: {category_name}")
        return ["No filters"]
    
    print(f"[Cat {category_index}] 🔍 Processing {len(filters)} filters for category: {category_name}")
    
    # Process filters in batches to avoid overwhelming the server
    max_concurrent_filters = config['scraping']['max_concurrent_filters']
    filter_batch_delay = config['scraping']['filter_batch_delay_seconds']
    
    all_results = []
    indexed_filters = list(enumerate(filters, 1))
    
    filter_chunks = [
        indexed_filters[i:i + max_concurrent_filters] 
        for i in range(0, len(indexed_filters), max_concurrent_filters)
    ]
    
    for i, chunk in enumerate(filter_chunks):
        print(f"[Cat {category_index}] 🚀 Processing filter batch {i + 1}/{len(filter_chunks)} with {len(chunk)} filters...")
        
        tasks = [
            scrape_filter_with_retry(
                browser, 
                device_config, 
                category_info, 
                filter_info, 
                responses_dir, 
                f"Cat{category_index}-F{filter_index}"
            )
            for filter_index, filter_info in chunk
        ]
        
        batch_results = await asyncio.gather(*tasks, return_exceptions=True)
        all_results.extend(batch_results)
        
        if i < len(filter_chunks) - 1:
            print(f"[Cat {category_index}] ✅ Filter batch {i + 1} complete. Waiting {filter_batch_delay} seconds...")
            await asyncio.sleep(filter_batch_delay)
    
    # Print category summary
    success_count = sum(1 for res in all_results if res == "Success")
    print(f"[Cat {category_index}] 📊 Category {category_name}: {success_count}/{len(filters)} filters scraped successfully")
    
    return all_results


async def scrape_all_category_filters(categories: List[Dict[str, Any]], responses_dir: Path) -> None:
    """Scrape filters for all categories in parallel batches."""
    config = load_config()
    max_concurrent_categories = config['scraping']['max_concurrent_categories']
    batch_delay = config['scraping']['batch_delay_seconds']
    
    async with async_playwright() as p:
        device_config = p.devices['Pixel 5']
        browser = await p.chromium.launch(headless=True)
        
        all_results = []
        indexed_categories = list(enumerate(categories, 1))
        
        category_chunks = [
            indexed_categories[i:i + max_concurrent_categories] 
            for i in range(0, len(indexed_categories), max_concurrent_categories)
        ]
        
        for i, chunk in enumerate(category_chunks):
            print(f"\n🚀 Processing category batch {i + 1}/{len(category_chunks)} with {len(chunk)} categories in parallel...")
            
            tasks = [
                scrape_category_filters(browser, device_config, category_info, responses_dir, category_index)
                for category_index, category_info in chunk
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(batch_results)
            
            if i < len(category_chunks) - 1:
                print(f"✅ Category batch {i + 1} complete. Waiting {batch_delay} seconds before next batch...")
                await asyncio.sleep(batch_delay)
        
        await browser.close()
        
        # Calculate overall statistics
        total_filters = sum(len(cat['filters']) for cat in categories)
        successful_filters = 0
        
        for category_results in all_results:
            if isinstance(category_results, list):
                successful_filters += sum(1 for res in category_results if res == "Success")
        
        print(f"\n🏁 Filter scraping completed!")
        print(f"📊 Overall Statistics:")
        print(f"   Categories processed: {len(categories)}")
        print(f"   Total filters: {total_filters}")
        print(f"   Successful filter scrapes: {successful_filters}")
        print(f"   Success rate: {(successful_filters/total_filters*100):.1f}%" if total_filters > 0 else "   Success rate: N/A")


def main():
    """Main function to scrape all category filters."""
    print("🚀 Starting Swiggy Filter Scraper (Step 3)...")
    
    try:
        # Load configuration
        config = load_config()
        responses_dir = Path(config['output']['base_directory'])
        
        if not responses_dir.exists():
            print(f"❌ Output directory not found: {responses_dir}")
            print("   Please run step1 and step2 first.")
            return 1
        
        # Load categories from step2 output
        print("📋 Loading categories from step2 output...")
        categories = load_categories_from_output(responses_dir)
        
        if not categories:
            print("❌ No categories found. Please run step2_scrape_categories.py first.")
            return 1
        
        # Filter out categories that have no filters
        categories_with_filters = [cat for cat in categories if cat['filters']]
        
        if not categories_with_filters:
            print("❌ No categories with filters found.")
            return 1
        
        print(f"🎯 Found {len(categories_with_filters)} categories with filters to process")
        
        # Calculate total filters
        total_filters = sum(len(cat['filters']) for cat in categories_with_filters)
        print(f"📊 Total filters to scrape: {total_filters}")
        
        # Start scraping
        print(f"\n🚀 Starting filter scraping...")
        asyncio.run(scrape_all_category_filters(categories_with_filters, responses_dir))
        
        print(f"\n🎉 Filter scraping completed!")
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
