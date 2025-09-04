#!/usr/bin/env python3
"""
Scraping utility functions for Swiggy category listings.
"""

import asyncio
import shutil
from pathlib import Path
from typing import Dict, Any, List, Optional, Set
from playwright.async_api import Browser, Page

from .common import (
    load_config, 
    convert_deeplink_to_web_url, 
    create_safe_filename,
    save_json,
    extract_initial_state_from_html
)


async def setup_api_interceptors(page: Page, api_responses: List[Dict], api_requests: List[Dict], index: int) -> None:
    """Set up API request and response interception for category listing calls."""
    
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


async def wait_for_initial_state(page: Page, index: int) -> Optional[Dict[str, Any]]:
    """Wait for and extract initial state from the page."""
    config = load_config()
    timeout = config['timeouts']['initial_state_timeout']
    
    print(f"[{index}] ⏳ Waiting for window.___INITIAL_STATE___ to be available...")
    try:
        await page.wait_for_function(
            "() => window.___INITIAL_STATE___ !== undefined",
            timeout=timeout
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
            return initial_state
        else:
            print(f"[{index}] ❌ window.___INITIAL_STATE___ is undefined or null")
    except Exception as e:
        print(f"[{index}] ❌ Error evaluating JavaScript: {e}")
    
    # If JavaScript failed, try HTML extraction as fallback
    print(f"[{index}] ⚠️ JavaScript extraction failed, trying HTML extraction...")
    html_content = await page.content()
    return extract_initial_state_from_html(html_content)


def is_valid_category_data(category_data: Dict[str, Any]) -> bool:
    """Check if categoryData is valid and not rate limited."""
    if not category_data:
        return False
    
    # Check if categoryData has essential data
    return bool(
        category_data.get('categories') or 
        category_data.get('filters') or 
        category_data.get('widgets')
    )


async def navigate_with_retry(page: Page, web_url: str, index: int) -> Optional[Dict[str, Any]]:
    """Navigate to category page with retry logic for rate limits."""
    config = load_config()
    max_retries = config['scraping']['max_retries']
    retry_delay = config['scraping']['retry_delay_seconds']
    page_timeout = config['timeouts']['page_load_timeout']
    
    retry_count = 0
    
    while retry_count < max_retries:
        if retry_count > 0:
            print(f"[{index}] 🔄 Retry {retry_count}/{max_retries} - Rate limit detected, refreshing page...")
            await asyncio.sleep(retry_delay)
        
        # Navigate to the category page
        await page.goto(web_url, wait_until="networkidle", timeout=page_timeout)
        
        # Wait for and extract initial state
        initial_state = await wait_for_initial_state(page, index)
        
        # Check if we got valid category data (not rate limited)
        if initial_state:
            category_data = initial_state.get('instamart', {}).get('categoryData', {})
            
            if is_valid_category_data(category_data):
                print(f"[{index}] ✅ Valid categoryData found with {len(category_data)} keys")
                return initial_state
            else:
                print(f"[{index}] ⚠️ Rate limited - categoryData is empty or incomplete. Retrying...")
                retry_count += 1
                continue
        else:
            print(f"[{index}] ⚠️ No initial state found. Retrying...")
            retry_count += 1
    
    return None


async def perform_smart_scroll(page: Page, index: int) -> Dict[str, Any]:
    """Perform smart scrolling to trigger pagination."""
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
    return scroll_result


async def trigger_mouse_interaction(page: Page, index: int) -> None:
    """Trigger mouse interaction to help with API calls."""
    print(f"[{index}] 🖱️ Adding mouse nudge to trigger fetch call...")
    viewport = page.viewport_size
    center_x = viewport['width'] // 2
    center_y = viewport['height'] // 2
    await page.mouse.move(center_x, center_y)
    await page.mouse.wheel(0, 200)


def check_api_error(response_data: Dict[str, Any]) -> bool:
    """Check if API response contains errors."""
    return (
        response_data.get('statusCode') == 'ERR_NON_2XX_3XX_RESPONSE' or 
        'stack' in response_data or 
        not response_data.get('data')
    )


async def process_pagination_responses(
    api_responses: List[Dict], 
    responses_before_scroll: int,
    category_dir: Path,
    safe_filename: str,
    saved_pages: Set[int],
    page_count: int,
    index: int
) -> tuple[bool, bool]:
    """
    Process new pagination API responses.
    Returns: (has_more, api_error_occurred)
    """
    config = load_config()
    
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
            if check_api_error(response_data):
                print(f"[{index}] ❌ API error response detected: {response_data}")
                print(f"[{index}] 🔄 API session corrupted, need to restart entire category with fresh browser context")
                return False, True  # has_more=False, api_error=True
            
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
                save_json(response_data, page_file)
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
            return has_more, False  # has_more, api_error=False
        else:
            print(f"[{index}] ⚠️ No valid responses in this batch, continuing...")
            return True, False  # Continue to try more
    else:
        print(f"[{index}] ⚠️ No new pagination API calls captured after scroll. Assuming end of list.")
        return False, False  # has_more=False, api_error=False


def cleanup_partial_data(category_dir: Path, index: int) -> None:
    """Clean up partial data from previous failed attempt."""
    if category_dir.exists():
        print(f"[{index}] 🧹 Cleaning up partial data from previous attempt...")
        shutil.rmtree(category_dir)
        print(f"[{index}] 🗑️ Removed directory: {category_dir}")


def print_scraping_summary(
    category_name: str, 
    api_requests: List[Dict], 
    api_responses: List[Dict], 
    saved_pages: Set[int], 
    index: int
) -> None:
    """Print summary of scraping results."""
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


def print_final_summary(all_results: List[str], total_categories: int) -> None:
    """Print final summary of all category scraping results."""
    print(f"\n🏁 Category scraping completed!")
    
    success_count = sum(1 for res in all_results if res == "Success")
    failures = [res for res in all_results if res != "Success"]
    
    print(f"✅ Successful scrapes: {success_count} / {total_categories}")
    if failures:
        print(f"❌ Failed scrapes: {len(failures)}")
        for i, failure in enumerate(failures[:5]):
            if isinstance(failure, Exception):
                print(f"   - Exception: {str(failure)}")
            else:
                print(f"   - {failure}")
        if len(failures) > 5:
            print(f"   - ... and {len(failures) - 5} more")
