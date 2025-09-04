#!/usr/bin/env python3
"""
Performs a full scrape of a category's filters by:
1. Navigating and priming the page with specific clicks.
2. For each filter, clicking it to load and save page 0.
3. Simulating scrolling and intercepting paginated API calls until all
   pages for that filter are downloaded.
"""

import asyncio
import json
from pathlib import Path
from playwright.async_api import async_playwright, Page, Locator, Response
from asyncio import TimeoutError

# To run this script:
# 1. Make sure you are in the ohara directory.
# 2. Install dependencies:
#    pip install playwright
# 3. Install browser binaries:
#    playwright install
# 4. Run the script from your terminal:
#    python scraper-v2/swiggy/test_playwright_listing_v2.py

async def handle_pagination_by_scrolling(page: Page, initial_page_data: dict, safe_filename_base: str, item_name: str):
    """
    Given the data from page 0, handles scrolling and capturing all
    subsequent paginated API responses.
    """
    has_more = initial_page_data.get("hasMore", False)

    while has_more:
        print(f"   ... Scrolling to trigger next page for '{item_name}'...")
        try:
            await page.wait_for_timeout(1000) # Polite pause before scroll
            
            async with page.expect_response("**/api/instamart/category-listing/filter**", timeout=15000) as response_info:
                await page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
            
            response = await response_info.value
            if response.ok:
                paginated_json = await response.json()
                data = paginated_json.get("data", {})
                if data:
                    page_no = data.get("pageNo")
                    has_more = data.get("hasMore", False)
                    
                    output_file_page_n = Path(f"{safe_filename_base}_page_{page_no}.json")
                    with open(output_file_page_n, 'w') as f:
                        json.dump(paginated_json, f, indent=2)
                    print(f"   -> Saved Page {page_no} data to {output_file_page_n}")
                    
                    if not has_more:
                         print(f"   -> Last page detected for '{item_name}'.")
                    else:
                        print("   -> Waiting 5 seconds before next scroll...")
                        await page.wait_for_timeout(5000)
                else:
                    print(f"   -> Paginated response had no 'data' field. Stopping.")
                    has_more = False
            else:
                print(f"   -> Paginated API request failed with status {response.status}. Stopping.")
                has_more = False
        except TimeoutError:
            print(f"   -> Timed out waiting for paginated response. Assuming end of list for '{item_name}'.")
            has_more = False

async def main():
    """Main function to navigate, prime the page, then sequentially scrape all filters."""
    initial_category_url = "https://www.swiggy.com/instamart/category-listing?categoryName=Fresh+Vegetables&custom_back=true&filterName=&offset=0&showAgeConsent=false&storeId=1392080&taxonomyType=Speciality+taxonomy+1"
    
    async with async_playwright() as p:
        device = p.devices['Pixel 5']
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(**device)
        page = await context.new_page()

        try:
            print(f"Navigating to: {initial_category_url}")
            await page.goto(initial_category_url, wait_until="load", timeout=60000)
            await page.wait_for_timeout(5000)

            filter_list_locator = page.locator("ul:has(li[data-itemid]) li[data-itemid]")
            
            print("Waiting for filter list to be visible...")
            await filter_list_locator.first.wait_for(state="visible", timeout=30000)
            
            # --- Priming Sequence ---
            print("\n--- Starting Priming Sequence ---")
            print("   -> Clicking second filter to prime the page...")
            await filter_list_locator.nth(1).click()
            await page.wait_for_timeout(3000)
            print("--- Priming Sequence Complete ---\n")

            filter_count = await filter_list_locator.count()
            print(f"   -> Found {filter_count} filters. Processing each one sequentially.")

            for i in range(filter_count):
                item_locator = filter_list_locator.nth(i)
                item_name = await item_locator.text_content()
                safe_filename_base = "".join(c for c in item_name if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')
                print(f"\n--- Processing Filter: {item_name} ---")

                try:
                    async with page.expect_response("**/api/instamart/category-listing/filter**", timeout=20000) as response_info:
                        await item_locator.hover()
                        await page.wait_for_timeout(250)
                        await item_locator.click()
                    
                    response = await response_info.value
                    if response.ok:
                        json_response = await response.json()
                        page_data = json_response.get("data", {})
                        
                        if page_data:
                            page_no = page_data.get("pageNo", 0)
                            output_file = Path(f"{safe_filename_base}_page_{page_no}.json")
                            with open(output_file, 'w') as f:
                                json.dump(json_response, f, indent=2)
                            print(f"   -> Saved Page {page_no} data to {output_file}")
                            
                            # Now handle pagination for this filter
                            await handle_pagination_by_scrolling(page, page_data, safe_filename_base, item_name)
                        else:
                            print(f"   -> API response for page 0 had no 'data' field.")
                    else:
                        print(f"   -> API request for page 0 failed with status {response.status}.")
                
                except Exception as e:
                    print(f"   -> An error occurred while processing filter '{item_name}': {e}")
                    screenshot_path = Path(f"debug_click_error_{safe_filename_base}.png")
                    await page.screenshot(path=screenshot_path)
                    print(f"   -> Screenshot saved to {screenshot_path}")

        except Exception as e:
            print(f"A critical error occurred: {e}")
            await page.screenshot(path="debug_critical_error.png")
            html_path = Path("debug_critical_error.html")
            with open(html_path, "w", encoding="utf-8") as f:
                f.write(await page.content())
            print(f"   -> Screenshot saved to debug_critical_error.png and HTML to {html_path}")
        
        finally:
            await context.close()
            await browser.close()
            print("\n🏁 Script finished.")

if __name__ == "__main__":
    asyncio.run(main())
