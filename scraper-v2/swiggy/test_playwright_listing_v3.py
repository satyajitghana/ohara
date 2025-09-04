#!/usr/bin/env python3
"""
Swiggy Home API Scraper - Version 3
Fetches category data from Swiggy's home API using Python requests
to avoid rate limiting issues with browser automation.
Then scrapes each category by opening the web URLs and saving HTML files.
"""

import asyncio
import json
import re
import requests
from pathlib import Path
from urllib.parse import parse_qs, urlparse, urlencode
from playwright.async_api import async_playwright
from bs4 import BeautifulSoup

MAX_CONCURRENT_CATEGORIES = 10 # Configurable number of parallel categories

def extract_store_id_from_url(url):
    """Extract storeId parameter from a Swiggy deeplink URL."""
    try:
        if "storeId=" in url:
            # Parse the URL and extract storeId
            parsed = urlparse(url)
            if parsed.query:
                params = parse_qs(parsed.query)
                return params.get('storeId', [None])[0]
    except Exception:
        pass
    return None

def extract_categories_from_response(api_response):
    """
    Extract category information from the Swiggy home API response.
    This version is more robust and handles cases where GridWidgets might be missing
    headers or other expected keys, which can happen with banner widgets.
    """
    categories = []
    
    try:
        data = api_response.get('data', {})
        cards = data.get('cards', [])
        
        print(f"Processing {len(cards)} cards from API response...")
        
        for card_index, card in enumerate(cards):
            # The actual card data can be nested one level down
            card_data = card.get('card', {}).get('card', {})
            card_type = card_data.get('@type', '')
            
            # We are only interested in GridWidgets that represent categories
            if card_type != 'type.googleapis.com/swiggy.gandalf.widgets.v2.GridWidget':
                continue

            # A valid category group must have a header with a title
            header = card_data.get('header')
            if not header or not header.get('title'):
                print(f"  -> Skipping GridWidget without a valid header title (likely a banner).")
                continue

            category_group_title = header.get('title')
            
            # The categories themselves are inside gridElements.infoWithStyle.info
            grid_elements = card_data.get('gridElements')
            if not grid_elements:
                continue
                
            info_with_style = grid_elements.get('infoWithStyle')
            if not info_with_style:
                continue

            info_items = info_with_style.get('info', [])
            if not info_items:
                continue

            print(f"  -> Found GridWidget '{category_group_title}' with {len(info_items)} items.")

            for item in info_items:
                action = item.get('action', {})
                link = action.get('link', '')
                
                # A valid category item must have a category-listing deeplink
                if 'swiggy://stores/instamart/category-listing' in link:
                    category_name = item.get('description')
                    if not category_name:
                        # Fallback for older formats or variations
                        parsed_link = urlparse(link)
                        query_params = parse_qs(parsed_link.query)
                        category_name = query_params.get('categoryName', [None])[0]
                    
                    if not category_name:
                        print(f"    ⏭️  Skipping item with no category name.")
                        continue

                    store_id = extract_store_id_from_url(link)
                    
                    category_info = {
                        'category_group_title': category_group_title,
                        'category_name': category_name,
                        'deeplink': link,
                        'store_id': store_id,
                        'widget_id': card_data.get('id', ''),
                        'image_id': item.get('imageId', ''),
                        'item_id': item.get('id', ''),
                        'analytics_l1_node': item.get('analytics', {}).get('extraFields', {}).get('l1NodeVal', '')
                    }
                    
                    categories.append(category_info)
                    print(f"    ✅ Found category: {category_name} (Group: {category_group_title})")
        
    except Exception as e:
        print(f"❌ Error parsing response: {e}")
        import traceback
        traceback.print_exc()
    
    return categories

def convert_deeplink_to_web_url(deeplink: str) -> str:
    """Convert Swiggy deeplink to web URL format."""
    # Extract parameters from deeplink
    if "?" in deeplink:
        query_part = deeplink.split("?", 1)[1]
        params = {}
        for param_pair in query_part.split("&"):
            if "=" in param_pair:
                key, value = param_pair.split("=", 1)
                params[key] = value
        
        # Add custom_back parameter
        params['custom_back'] = 'true'
        
        # Build web URL
        base_url = "https://www.swiggy.com/instamart/category-listing"
        return f"{base_url}?{urlencode(params)}"
    
    return deeplink

def extract_initial_state_from_html(html_content: str) -> dict:
    """Extract ___INITIAL_STATE___ JSON from HTML content."""
    try:
        soup = BeautifulSoup(html_content, 'html.parser')
        initial_state_script = soup.find('script', string=re.compile(r'window\.___INITIAL_STATE___'))
        
        if initial_state_script:
            script_content = initial_state_script.string
            match = re.search(r'window\.___INITIAL_STATE___\s*=\s*(\{.*?\});', script_content, re.DOTALL)
            
            if match:
                json_text = match.group(1)
                return json.loads(json_text)
        
    except Exception as e:
        print(f"❌ Error extracting initial state: {e}")
    
    return {}

async def scrape_category_with_pagination(browser, device_config: dict, category: dict, responses_dir: Path, index: int):
    """Scrape a single category, creating its own browser context, and capture paginated API calls."""
    category_name = category['category_name']
    safe_filename = "".join(c for c in category_name if c.isalnum() or c in (' ', '_')).rstrip().replace(' ', '_')
    
    print(f"[{index}] 🌐 Starting scrape for: {category_name}")
    
    # Retry mechanism for entire category when API errors occur
    max_category_retries = 5
    category_retry_count = 0
    
    while category_retry_count < max_category_retries:
        if category_retry_count > 0:
            print(f"[{index}] 🔄 Category retry {category_retry_count}/{max_category_retries} for {category_name} due to API errors")
            await asyncio.sleep(5)  # Wait longer between category retries
            
            # Clean up any partial data from previous failed attempt
            category_dir = responses_dir / safe_filename
            if category_dir.exists():
                print(f"[{index}] 🧹 Cleaning up partial data from previous attempt...")
                import shutil
                shutil.rmtree(category_dir)
                print(f"[{index}] 🗑️ Removed directory: {category_dir}")
        
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

async def scrape_category_attempt(browser, device_config: dict, category: dict, responses_dir: Path, index: int, safe_filename: str):
    """Single attempt to scrape a category."""
    category_name = category['category_name']
    
    context = await browser.new_context(**device_config)
    print(f"[{index}] 📱 Context created for {category_name}")
    
    try:
        # Create page using the context
        page = await context.new_page()
        
        print(f"[{index}] 📱 Using Pixel 5 device configuration for {category_name}")
        
        # Set up API request and response interception
        api_responses = []
        api_requests = []
        
        async def handle_request(request):
            if "/api/instamart/category-listing" in request.url:
                request_info = {
                    'method': request.method,
                    'url': request.url,
                    'headers': dict(request.headers),
                    'post_data': None
                }
                
                if request.method == "POST":
                    try:
                        request_info['post_data'] = request.post_data
                        print(f"[{index}] 📤 POST REQUEST to: {request.url}")
                        print(f"[{index}] 📤 POST DATA: {request.post_data}")
                    except Exception as e:
                        print(f"[{index}] ⚠️ Failed to get POST data: {e}")
                
                api_requests.append(request_info)
                print(f"[{index}] 🌐 {request.method} request to: {request.url}")
        
        async def handle_response(response):
            if "/api/instamart/category-listing" in response.url:
                try:
                    response_data = await response.json()
                    api_responses.append({
                        'url': response.url,
                        'method': response.request.method,
                        'status': response.status,
                        'data': response_data
                    })
                    print(f"[{index}] 📡 Captured {response.request.method} response from: {response.url}")
                    if response.request.method == "POST":
                        print(f"[{index}] 📡 Response status: {response.status}")
                except Exception as e:
                    print(f"[{index}] ⚠️ Failed to parse API response: {e}")
        
        page.on('request', handle_request)
        page.on('response', handle_response)
        
        # Convert deeplink to web URL
        web_url = convert_deeplink_to_web_url(category['deeplink'])
        print(f"[{index}] URL: {web_url}")
        
        # Create category-specific directory
        category_dir = responses_dir / safe_filename
        category_dir.mkdir(exist_ok=True)
        
        # Retry mechanism for handling rate limits
        max_retries = 5
        retry_count = 0
        initial_state = None
        
        while retry_count < max_retries:
            if retry_count > 0:
                print(f"[{index}] 🔄 Retry {retry_count}/{max_retries} - Rate limit detected, refreshing page...")
                await asyncio.sleep(3)  # Wait before retry
            
            # Navigate to the category page
            await page.goto(web_url, wait_until="networkidle", timeout=60000)
            
            # Wait for the specific content we need to be available
            print(f"[{index}] ⏳ Waiting for window.___INITIAL_STATE___ to be available...")
            try:
                await page.wait_for_function(
                    "() => window.___INITIAL_STATE___ !== undefined",
                    timeout=30000
                )
                print(f"[{index}] ✅ window.___INITIAL_STATE___ is available")
            except Exception as e:
                print(f"[{index}] ⚠️ Timeout waiting for window.___INITIAL_STATE___: {e}")
            
            # Additional wait to ensure all dynamic content is loaded
            await asyncio.sleep(3)
            
            # Try to extract initial state from JavaScript execution first (more reliable)
            try:
                initial_state = await page.evaluate("() => window.___INITIAL_STATE___")
                if initial_state:
                    print(f"[{index}] ✅ Successfully extracted initial state via JavaScript evaluation")
                else:
                    print(f"[{index}] ❌ window.___INITIAL_STATE___ is undefined or null")
            except Exception as e:
                print(f"[{index}] ❌ Error evaluating JavaScript: {e}")
            
            # If JavaScript failed, try HTML extraction as fallback
            if not initial_state:
                print(f"[{index}] ⚠️ JavaScript extraction failed, trying HTML extraction...")
                html_content = await page.content()
                initial_state = extract_initial_state_from_html(html_content)
            
            # Check if we got valid category data (not rate limited)
            if initial_state:
                category_data = initial_state.get('instamart', {}).get('categoryData', {})
                
                # Check if categoryData is empty or missing essential data
                if not category_data or (
                    not category_data.get('categories') and 
                    not category_data.get('filters') and 
                    not category_data.get('widgets')
                ):
                    print(f"[{index}] ⚠️ Rate limited - categoryData is empty or incomplete. Retrying...")
                    initial_state = None  # Reset to trigger retry
                    retry_count += 1
                    continue
                else:
                    print(f"[{index}] ✅ Valid categoryData found with {len(category_data)} keys")
                    break  # Success - exit retry loop
            else:
                print(f"[{index}] ⚠️ No initial state found. Retrying...")
                retry_count += 1
        
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
            soup = BeautifulSoup(html_content, 'html.parser')
            scripts = soup.find_all('script')
            print(f"[{index}] 🐛 Found {len(scripts)} script tags")
            
            # Look for any script containing "INITIAL_STATE"
            initial_state_scripts = [s for s in scripts if s.string and 'INITIAL_STATE' in s.string]
            print(f"[{index}] 🐛 Found {len(initial_state_scripts)} scripts containing 'INITIAL_STATE'")
            
            if initial_state_scripts:
                print(f"[{index}] 🐛 First INITIAL_STATE script preview: {initial_state_scripts[0].string[:200]}...")
            
            print(f"[{index}] ❌ CRITICAL: Could not get valid data after {max_retries} retries. Aborting scrape for this category.")
            return f"Failed - No valid data after {max_retries} retries"
        
        initial_state_file = category_dir / f"{safe_filename}_initial_state.json"
        with open(initial_state_file, 'w') as f:
            json.dump(initial_state, f, indent=2)
        print(f"[{index}] 💾 Saved initial state to {initial_state_file}")
        
        category_data = initial_state.get('instamart', {}).get('categoryData', {})
        saved_pages = set()  # Track which pages we've already saved
        
        if category_data:
            # Wrap data to match the structure of paginated API calls for consistency
            page_0_data = {"data": category_data}
            category_data_file = category_dir / f"{safe_filename}_page_0.json"
            with open(category_data_file, 'w') as f:
                json.dump(page_0_data, f, indent=2)
            print(f"[{index}] 💾 Saved page 0 data to {category_data_file}")
            saved_pages.add(0)  # Mark page 0 as saved
        
        # Now scroll to trigger pagination
        print(f"[{index}] 🔄 Starting pagination by scrolling...")
        
        page_count = 1
        has_more = True
        max_scroll_loops = 20
        
        while has_more and page_count <= max_scroll_loops:
            print(f"[{index}] ⬇️ Scroll loop iteration {page_count}...")
            
            post_filter_responses_before = [
                r for r in api_responses 
                if "/api/instamart/category-listing/filter" in r.get('url', '') and r.get('method') == 'POST'
            ]
            responses_before_scroll = len(post_filter_responses_before)

            try:
                # screenshot_before = category_dir / f"{safe_filename}_before_scroll_{page_count}.png"
                # await page.screenshot(path=screenshot_before)
                # print(f"[{index}] 📸 Screenshot before scroll saved: {screenshot_before}")
                
                print(f"[{index}] 🔄 Starting smart scroll to trigger pagination...")
                scroll_result = await page.evaluate('''
                    (async () => {
                        async function scrollToBottomWithLastItem() {
                            const container = document.getElementById('bottom-hud-wrapper');
                            if (!container) {
                                console.error('Scroll container not found.');
                                return { success: false, message: 'Container not found' };
                            }
                            let lastItemHTML = '';
                            let attempts = 0;
                            const maxAttempts = 20;
                            while (attempts < maxAttempts) {
                                const items = container.querySelectorAll('div[data-testid="ItemWidgetContainer"]');
                                if (items.length === 0) {
                                    console.log('No items to scroll.');
                                    return { success: false, message: 'No items found', attempts };
                                }
                                const currentLastItem = items[items.length - 1];
                                const currentLastItemHTML = currentLastItem.outerHTML;
                                if (lastItemHTML === currentLastItemHTML) {
                                    console.log('Reached the bottom of the list.');
                                    currentLastItem.scrollIntoView({ behavior: 'auto', block: 'end' });
                                    return { success: true, message: 'Reached bottom', attempts, itemCount: items.length };
                                }
                                lastItemHTML = currentLastItemHTML;
                                currentLastItem.scrollIntoView({ behavior: 'smooth', block: 'end' });
                                await new Promise(resolve => setTimeout(resolve, 1500));
                                attempts++;
                            }
                            if (attempts >= maxAttempts) {
                                console.warn('Max scroll attempts reached. The list may be incomplete.');
                                return { success: false, message: 'Max attempts reached', attempts };
                            }
                        }
                        return await scrollToBottomWithLastItem();
                    })()
                ''')
                print(f"[{index}] 📊 Scroll result: {scroll_result}")
                
                # screenshot_after = category_dir / f"{safe_filename}_after_scroll_{page_count}.png"
                # await page.screenshot(path=screenshot_after)
                # print(f"[{index}] 📸 Screenshot after scroll saved: {screenshot_after}")
                
                print(f"[{index}] 🖱️ Adding mouse nudge to trigger fetch call...")
                viewport = page.viewport_size
                center_x = viewport['width'] // 2
                center_y = viewport['height'] // 2
                await page.mouse.move(center_x, center_y)
                await page.mouse.wheel(0, 200)
                
                print(f"[{index}] ⏳ Waiting for API responses to be captured...")
                await asyncio.sleep(4)

                post_filter_responses_after = [
                    r for r in api_responses 
                    if "/api/instamart/category-listing/filter" in r.get('url', '') and r.get('method') == 'POST'
                ]

                if len(post_filter_responses_after) > responses_before_scroll:
                    new_responses = post_filter_responses_after[responses_before_scroll:]
                    print(f"[{index}] 📡 {len(new_responses)} new API responses were captured.")
                    
                    # Check for API errors and save valid responses
                    valid_responses = []
                    for response in new_responses:
                        response_data = response.get('data', {})
                        
                        # Check if this is an error response - if so, immediately restart category
                        if (response_data.get('statusCode') == 'ERR_NON_2XX_3XX_RESPONSE' or 
                            'stack' in response_data or 
                            not response_data.get('data')):
                            print(f"[{index}] ❌ API error response detected: {response_data}")
                            print(f"[{index}] 🔄 API session corrupted, need to restart entire category with fresh browser context")
                            return "Failed - API_ERROR - Session corrupted"
                        
                        valid_responses.append(response)
                        nested_data = response_data.get('data', {})
                        
                        # Ensure pageNo is always an integer
                        try:
                            page_no = int(nested_data.get('pageNo', page_count))
                        except (ValueError, TypeError):
                            print(f"[{index}] ⚠️ Invalid pageNo in response, using page_count: {page_count}")
                            page_no = page_count
                        
                        # Only save if we haven't saved this page yet
                        if page_no not in saved_pages:
                            page_file = category_dir / f"{safe_filename}_page_{page_no}.json"
                            with open(page_file, 'w') as f:
                                json.dump(response_data, f, indent=2)
                            print(f"[{index}] 💾 Saved page {page_no} data to {page_file}")
                            saved_pages.add(page_no)
                        else:
                            print(f"[{index}] ⏭️ Page {page_no} already saved, skipping")
                    
                    # Use the latest valid response to determine if we should continue
                    if valid_responses:
                        latest_response = valid_responses[-1]
                        response_data = latest_response.get('data', {})
                        nested_data = response_data.get('data', {})
                        has_more = nested_data.get('hasMore', False)
                        print(f"[{index}] 📊 Latest valid API response 'hasMore': {has_more}")
                    else:
                        print(f"[{index}] ⚠️ No valid responses in this batch, continuing...")
                        has_more = True  # Continue to try more

                else:
                    print(f"[{index}] ⚠️ No new pagination API calls captured after scroll. Assuming end of list.")
                    has_more = False
                    
            except Exception as e:
                print(f"[{index}] ⚠️ Error during scroll/pagination loop: {e}")
                has_more = False

            if not has_more:
                print(f"[{index}] ✅ Reached last page for {category_name}.")
                break
            
            page_count += 1
            await asyncio.sleep(2)
        
        if api_requests:
            api_requests_file = category_dir / f"{safe_filename}_api_requests.json"
            with open(api_requests_file, 'w') as f:
                json.dump(api_requests, f, indent=2)
            print(f"[{index}] 💾 Saved {len(api_requests)} API requests to {api_requests_file}")
        
        if api_responses:
            api_responses_file = category_dir / f"{safe_filename}_api_responses.json"
            with open(api_responses_file, 'w') as f:
                json.dump(api_responses, f, indent=2)
            print(f"[{index}] 💾 Saved {len(api_responses)} API responses to {api_responses_file}")
        
        print(f"\n[{index}] 📊 API CALLS SUMMARY for {category_name}:")
        print(f"[{index}] 📤 Total Requests: {len(api_requests)}")
        print(f"[{index}] 📡 Total Responses: {len(api_responses)}")
        
        post_requests = [req for req in api_requests if req['method'] == 'POST']
        if post_requests:
            print(f"[{index}] 🔥 POST REQUESTS:")
            for i, req in enumerate(post_requests, 1):
                print(f"[{index}]   {i}. {req['url']}")
                if req['post_data']:
                    print(f"[{index}]      Data: {req['post_data']}")
        else:
            print(f"[{index}] ❌ No POST requests found!")
        
        print(f"\n[{index}] 📄 PAGES SAVED SUMMARY for {category_name}:")
        print(f"[{index}] 💾 Total pages saved: {len(saved_pages)}")
        # Ensure all pages are integers for proper sorting
        try:
            sorted_pages = sorted([int(p) for p in saved_pages if str(p).isdigit()])
            print(f"[{index}] 📝 Pages: {sorted_pages}")
        except Exception as e:
            print(f"[{index}] 📝 Pages (unsorted due to mixed types): {list(saved_pages)}")
        
        return "Success"
        
    except Exception as e:
        print(f"[{index}] ❌ Error scraping {category_name}: {e}")
        return f"Failed - {str(e)}"
    finally:
        await context.close()
        print(f"[{index}] 🔒 Context closed for {category_name}.")

async def scrape_all_categories(categories: list, responses_dir: Path):
    """Scrape all categories in parallel batches."""
    async with async_playwright() as p:
        device_config = p.devices['Pixel 5']
        browser = await p.chromium.launch(headless=True)
        
        all_results = []
        indexed_categories = list(enumerate(categories, 1))
        
        category_chunks = [indexed_categories[i:i + MAX_CONCURRENT_CATEGORIES] for i in range(0, len(indexed_categories), MAX_CONCURRENT_CATEGORIES)]
        
        for i, chunk in enumerate(category_chunks):
            print(f"\n🚀 Processing batch {i + 1}/{len(category_chunks)} with {len(chunk)} categories in parallel...")
            
            tasks = [
                scrape_category_with_pagination(browser, device_config, category, responses_dir, index)
                for index, category in chunk
            ]
            
            batch_results = await asyncio.gather(*tasks, return_exceptions=True)
            all_results.extend(batch_results)
            
            if i < len(category_chunks) - 1:
                print(f"✅ Batch {i + 1} complete. Waiting 5 seconds before next batch...")
                await asyncio.sleep(5)
        
        await browser.close()
        
        print(f"\n🏁 Category scraping completed!")
        
        success_count = sum(1 for res in all_results if res == "Success")
        failures = [res for res in all_results if res != "Success"]
        
        print(f"✅ Successful scrapes: {success_count} / {len(categories)}")
        if failures:
            print(f"❌ Failed scrapes: {len(failures)}")
            for i, failure in enumerate(failures[:5]):
                if isinstance(failure, Exception):
                    print(f"   - Exception: {str(failure)}")
                else:
                    print(f"   - {failure}")
            if len(failures) > 5:
                print(f"   - ... and {len(failures) - 5} more")

def fetch_swiggy_home_categories():
    """Fetch categories from Swiggy's home API."""
    
    # API endpoint
    url = "https://www.swiggy.com/api/instamart/home/v2"
    
    # Query parameters
    params = {
        'offset': '1',
        'layoutId': '4987',
        'storeId': '1392080',
        'primaryStoreId': '1392080',
        'secondaryStoreId': '1396284',
        'clientId': 'INSTAMART-APP'
    }
    
    # Headers from the curl command
    headers = {
        'accept': '*/*',
        'accept-language': 'en-US,en;q=0.9',
        'content-type': 'application/json',
        'if-none-match': 'W/"164b5-oWiVsm21fZmyX1LgyDJsBPspc3A"',
        'matcher': 'acb7f8ecdf99dbe79bg9c8b',
        'priority': 'u=1, i',
        'referer': 'https://www.swiggy.com/instamart',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'x-build-version': '2.292.0'
    }
    
    # Cookies from the curl command
    cookies = {
        '__SW': 'q2ozkEoBpNOUZGtU2zOzErGUlW5fJX49',
        '_device_id': 'a6d1fc28-603d-a959-7185-dc042f63e01e',
        'fontsLoaded': '1',
        '_gcl_au': '1.1.304394544.1756804512',
        '_gid': 'GA1.2.584754363.1756804512',
        'dadl': 'true',
        'application_name': '',
        'category': '',
        'x-channel': '',
        'x-theme': '',
        '_swuid': 'a6d1fc28-603d-a959-7185-dc042f63e01e',
        '_ga_34JYJ0BCRN': 'GS2.1.s1756804512$o1$g1$t1756804539$j33$l0$h0',
        '_ga_YE38MFJRBZ': 'GS2.1.s1756804512$o1$g1$t1756804539$j33$l0$h0',
        'deliveryAddressId': '',
        'deviceId': 's%3Aa6d1fc28-603d-a959-7185-dc042f63e01e.6HZLM5jn8OjHX%2FYfrs8hPanxyoluYsnKrWzPaWf8WK8',
        'tid': 's%3A090e3d33-18ec-4656-b66a-0b3f790cf1b9.kllo01piwvWwaZ0nVennWDyK9qsysll9TOUJpo62pF0',
        'versionCode': '1200',
        'platform': 'web',
        'statusBarHeight': '0',
        'bottomOffset': '0',
        'genieTrackOn': 'false',
        'ally-on': 'false',
        'isNative': 'false',
        'strId': '',
        'openIMHP': 'false',
        'lat': 's%3A12.9110344.e9lmVysp87FnZ0lB3AWtxWOAY8BMM8lvVj3uVRKsFK0',
        'lng': 's%3A77.6307796.DBFQyCGUQGExTPxJokHfTZnJaC3Q%2FSh7U%2Fiw%2BZnR0RI',
        'address': 's%3AGround%20Floor%2C%20Site%20No.%2071%2C%202%20%26%2071%2F2A%2C%203rd%20Main%20Rd%2C.faH9NrbWswNmkpVzQDPHl3X60Ba3Gtj%2FB3k2Pzs2fu8',
        'addressId': 's%3A.4Wx2Am9WLolnmzVcU32g6YaFDw0QbIBFRj2nkO7P25s',
        'LocSrc': 's%3AswgyUL.Dzm1rLPIhJmB3Tl2Xs6141hVZS0ofGP7LGmLXgQOA7Y',
        '_fbp': 'fb.1.1756804554438.620488998775308354',
        'sid': 's%3Amn22bc5f-8300-4eff-9c7d-b1c06f9bc973.HxJgwL%2BYenDSQt%2FqwqLoPDnfKN%2BJnWRQpPNDLzlnEe0',
        'subplatform': 'mweb',
        '_guest_tid': '51220a95-395d-4164-92f3-61aeaa48cbe7',
        '_is_logged_in': '',
        '_sid': 'mn7bb846-ff7f-48b4-baeb-e4485b94d8cd',
        'AMP_TOKEN': '%24NOT_FOUND',
        '_ga_X3K3CELKLV': 'GS2.1.s1756821263$o2$g0$t1756821264$j59$l0$h0',
        'userLocation': '%7B%22address%22%3A%22Ground%20Floor%2C%20Site%20No.%2071%2C%202%20%26%2071%2F2A%2C%203rd%20Main%20Rd%2C%20Phase%203%2C%207th%20Sector%2C%20HSR%20Layout%2C%20Bengaluru%2C%20Karnataka%20560102%2C%20India%22%2C%22lat%22%3A12.9110344%2C%22lng%22%3A77.6307796%2C%22id%22%3A%22%22%2C%22annotation%22%3A%22%22%2C%22name%22%3A%22%22%7D',
        '_ga': 'GA1.1.1791705685.1756804512',
        'isImBottomBarXpEnabled': 's%3Atrue.e48T%2B1OIqhnOplwfDLfBpm6ciWJemq9CxKQOhhXd4VA',
        'webBottomBarHeight': '64',
        '_ga_VEG1HFE5VZ': 'GS2.1.s1756814614$o2$g1$t1756822646$j52$l0$h0',
        '_ga_0XZC5MS97H': 'GS2.1.s1756814614$o2$g1$t1756822646$j52$l0$h0',
        '_ga_8N8XRG907L': 'GS2.1.s1756814614$o2$g1$t1756822646$j52$l0$h0',
        'aws-waf-token': 'ce88556a-3204-4b78-99d9-0c51074aa9b6:HgoAgGRje0IBAQAA:la3bhbtNNhYwO2foPDJ3CLn6jag7KEkr2fqRq8WQYU/xLZR7wrKstsP57uyrRXXtMmJj60lkVNoiJ/JBlnMn6ABGdd29V2XWTFHORUTdccjFvcs1XbYXoyvHS6sqiU9MYAdkvuSVGwbHA8w17x5YQNki2361Tvg8C0pyYp+5mGCXaM7+MzJelr0nSpmACeHqrQsBeTinrCMijKnHw9fHBZ2eWlC2CBtSR3PgX9tqHI2lhXUSYrMaSrA3awNJAzY='
    }
    
    print("🚀 Fetching Swiggy home API...")
    
    try:
        response = requests.get(url, params=params, headers=headers, cookies=cookies, timeout=30)
        
        if response.status_code == 200:
            print("✅ Successfully fetched home API response")
            return response.json()
        else:
            print(f"❌ API request failed with status code: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Network error occurred: {e}")
        return None

def main():
    """Main function to fetch and process Swiggy categories."""
    print("🚀 Starting Swiggy Category Scraper v3...")
    
    # Fetch the home API response
    api_response = fetch_swiggy_home_categories()
    
    if not api_response:
        print("❌ Failed to fetch API response. Exiting.")
        return
    
    # Create responses-v3 folder
    responses_dir = Path("responses-v3")
    responses_dir.mkdir(exist_ok=True)
    print(f"📁 Created/verified responses-v3 directory")
    
    # Save the raw API response for debugging
    raw_response_path = responses_dir / "playwright-swiggy-home-raw.json"
    with open(raw_response_path, 'w') as f:
        json.dump(api_response, f, indent=2)
    print(f"💾 Raw API response saved to {raw_response_path}")
    
    # Extract categories from the response
    print("\n🔍 Extracting categories from API response...")
    categories = extract_categories_from_response(api_response)
    
    if categories:
        # Save extracted categories
        output_path = responses_dir / "playwright-swiggy-home.json"
        output_data = {
            'total_categories': len(categories),
            'extracted_at': api_response.get('data', {}).get('pageOffset', {}).get('nextOffset', ''),
            'categories': categories
        }
        
        with open(output_path, 'w') as f:
            json.dump(output_data, f, indent=2)
        
        print(f"\n✅ SUCCESS: Extracted {len(categories)} categories")
        print(f"💾 Data saved to {output_path}")
        
        # Print summary of category groups
        groups = {}
        for cat in categories:
            group = cat['category_group_title']
            if group not in groups:
                groups[group] = []
            groups[group].append(cat['category_name'])
        
        print(f"\n📊 Category Groups Summary:")
        for group, items in groups.items():
            print(f"   🏷️  {group}: {len(items)} categories")
        
        # Now scrape each category
        print(f"\n🚀 Starting category scraping...")
        asyncio.run(scrape_all_categories(categories, responses_dir))
            
    else:
        print("❌ No categories found in the API response")

if __name__ == "__main__":
    main()
