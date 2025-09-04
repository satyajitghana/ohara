#!/usr/bin/env python3
"""
Test script to fetch multiple category listings in parallel using Playwright 
by extracting the ___INITIAL_STATE___ JSON from the page's HTML.
"""

import asyncio
import json
import re
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from bs4 import BeautifulSoup

def load_home_categories() -> list[dict]:
    """Loads all category objects from the home.json file."""
    home_file = Path("responses-v2/home.json")
    if not home_file.exists():
        print("❌ FAILED: responses-v2/home.json not found. Please run Step 1 first.")
        return []
    
    with open(home_file, 'r') as f:
        data = json.load(f)
    
    categories = data.get("categories", [])
    
    print(f"✓ Loaded {len(categories)} categories from home.json.")
    return categories

def parse_deeplink_params(deeplink: str) -> dict[str, str]:
    """Extract parameters from Swiggy deeplink URL, handling age consent wrappers."""
    from urllib.parse import unquote
    
    if deeplink.startswith("swiggy://ageConsent"):
        if "url=" in deeplink:
            encoded_url = deeplink.split("url=", 1)[1]
            deeplink = unquote(encoded_url) # decode the inner url
    
    params = {}
    if "?" in deeplink:
        query_part = deeplink.split("?", 1)[1]
        for param_pair in query_part.split("&"):
            if "=" in param_pair:
                key, value = param_pair.split("=", 1)
                params[key] = value
    return params

def get_category_url(category: dict) -> str:
    """Generates a Swiggy Instamart category URL from a category object's deeplink."""
    base_url = "https://www.swiggy.com/instamart/category-listing"
    
    # Extract params from the authoritative deeplink
    params = parse_deeplink_params(category["deeplink"])
    
    # Ensure custom_back is present as it seems to be needed for web view
    params.setdefault("custom_back", "true")
    
    from urllib.parse import urlencode
    return f"{base_url}?{urlencode(params)}"


async def fetch_category(browser, category: dict, index: int):
    """
    Worker function to launch a browser, navigate, and scrape the initial state for one category,
    with exponential backoff for rate limiting.
    """
    category_name = category["category_name"]
    output_file = f"playwright_parallel_test_{category_name.replace(' ', '_')}.json"
    
    print(f"[{index}] 🚀 Starting worker for: {category_name}")
    
    # Print the URL for manual verification
    target_url = get_category_url(category)
    print(f"[{index}] Navigating to URL: {target_url}")
    
    max_retries = 10
    base_backoff_seconds = 5.0
    
    for attempt in range(max_retries):
        page = None
        try:
            page = await browser.new_page()
            
            if attempt > 0:
                print(f"[{index}] Retrying ({attempt + 1}/{max_retries}) for {category_name}...")
                
            await page.goto(target_url, wait_until="networkidle", timeout=60000)
            
            html_content = await page.content()
            soup = BeautifulSoup(html_content, 'html.parser')
            
            initial_state_script = soup.find('script', string=re.compile(r'window\.___INITIAL_STATE___'))
            
            if initial_state_script:
                script_content = initial_state_script.string
                match = re.search(r'window\.___INITIAL_STATE___\s*=\s*(\{.*?\});', script_content, re.DOTALL)
                
                if match:
                    json_text = match.group(1)
                    json_data = json.loads(json_text)
                    
                    category_data = json_data.get("instamart", {}).get("categoryData", {})
                    if category_data and (category_data.get("categories") or category_data.get("filters")):
                        output_path = Path(output_file)
                        with open(output_path, 'w') as f:
                            json.dump(json_data, f, indent=2)
                        
                        print(f"[{index}] ✅ SUCCESS on attempt {attempt + 1} for {category_name}. Saved to {output_file}")
                        return "Success"
                    else:
                        print(f"[{index}] ⚠️ Rate limited on attempt {attempt + 1} (empty categoryData) for {category_name}.")
                else:
                    print(f"[{index}] ⚠️ No JSON match on attempt {attempt + 1} for {category_name}.")
            else:
                print(f"[{index}] ⚠️ No ___INITIAL_STATE___ script found on attempt {attempt + 1} for {category_name}.")
                
        except PlaywrightTimeoutError:
            print(f"[{index}] ⚠️ Timeout on attempt {attempt + 1} for {category_name}.")
        except Exception as e:
            print(f"[{index}] ⚠️ Error on attempt {attempt + 1} for {category_name}: {e}")
        
        finally:
            if page:
                await page.close()

        # If we got here, it's a failure for this attempt. Wait before the next one.
        if attempt < max_retries - 1:
            delay = base_backoff_seconds * (2 ** attempt)
            print(f"[{index}] ⏳ Backing off for {delay:.1f}s...")
            await asyncio.sleep(delay)
    
    print(f"[{index}] ❌ FAILED: Max retries ({max_retries}) reached for {category_name}.")
    return f"Failed - Max Retries ({category_name})"

def chunks(lst, n):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]

async def main():
    print("🚀 Starting Playwright parallel test for all categories from home.json (in chunks of 10)...")
    
    all_categories = load_home_categories()
    if not all_categories:
        return
    
    # Filter out categories with age consent
    filtered_categories = []
    skipped_categories = []
    
    for category in all_categories:
        if "ageConsent" in category.get("deeplink", ""):
            skipped_categories.append(category["category_name"])
        else:
            filtered_categories.append(category)
    
    if skipped_categories:
        print(f"⚠️ Skipping {len(skipped_categories)} categories with age consent: {', '.join(skipped_categories)}")
    
    all_categories = filtered_categories
    print(f"✓ Processing {len(all_categories)} categories (after filtering age consent)")
    
    if not all_categories:
        print("❌ No categories to process after filtering.")
        return
        
    all_results = []
    chunk_size = 10
    
    # Process the categories in chunks of 10
    for i, chunk in enumerate(chunks(all_categories, chunk_size)):
        print(f"\n--- Starting Chunk {i + 1}/{ (len(all_categories) + chunk_size - 1) // chunk_size } ---")
        
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            
            # Create a list of tasks for the current chunk
            tasks = [fetch_category(browser, name, j + (i * chunk_size) + 1) for j, name in enumerate(chunk)]
            
            # Run tasks for the current chunk concurrently
            results = await asyncio.gather(*tasks)
            all_results.extend(results)
            
            await browser.close()
        
        print(f"--- Finished Chunk {i + 1} ---")

    print("\n🏁 Playwright parallel test finished for all chunks.")
    
    # --- Final Summary ---
    print("\n--- Final Test Summary ---")
    success_count = all_results.count("Success")
    failures = [res for res in all_results if res != "Success"]
    
    print(f"   ✅ Successful scrapes: {success_count} / {len(all_categories)}")
    if failures:
        print(f"   ❌ Failed scrapes: {len(failures)}")
        for i, failure in enumerate(failures):
            print(f"      - Failure {i+1}: {failure}")

if __name__ == "__main__":
    asyncio.run(main())
