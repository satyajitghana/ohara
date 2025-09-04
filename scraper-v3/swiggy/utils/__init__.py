"""
Utilities package for Swiggy scraper.
Contains common functions, API utilities, and scraping utilities.
"""

from .common import (
    load_config,
    get_store_config,
    extract_store_id_from_url,
    convert_deeplink_to_web_url,
    create_safe_filename,
    ensure_directory,
    save_json,
    load_json,
    extract_initial_state_from_html,
    print_summary_header,
    print_category_summary,
    print_directory_structure_summary,
    extract_filters_from_category_data,
    build_filter_url,
    load_categories_from_output
)

from .api import (
    build_home_api_url,
    build_home_api_params,
    get_api_headers,
    get_api_cookies,
    fetch_swiggy_home_api,
    extract_categories_from_response
)

from .scraper import (
    setup_api_interceptors,
    wait_for_initial_state,
    is_valid_category_data,
    navigate_with_retry,
    perform_smart_scroll,
    trigger_mouse_interaction,
    check_api_error,
    process_pagination_responses,
    cleanup_partial_data,
    print_scraping_summary,
    print_final_summary
)

__all__ = [
    # Common utilities
    'load_config',
    'get_store_config',
    'extract_store_id_from_url',
    'convert_deeplink_to_web_url',
    'create_safe_filename',
    'ensure_directory',
    'save_json',
    'load_json',
    'extract_initial_state_from_html',
    'print_summary_header',
    'print_category_summary',
    'print_directory_structure_summary',
    'extract_filters_from_category_data',
    'build_filter_url',
    'load_categories_from_output',
    
    # API utilities
    'build_home_api_url',
    'build_home_api_params',
    'get_api_headers',
    'get_api_cookies',
    'fetch_swiggy_home_api',
    'extract_categories_from_response',
    
    # Scraping utilities
    'setup_api_interceptors',
    'wait_for_initial_state',
    'is_valid_category_data',
    'navigate_with_retry',
    'perform_smart_scroll',
    'trigger_mouse_interaction',
    'check_api_error',
    'process_pagination_responses',
    'cleanup_partial_data',
    'print_scraping_summary',
    'print_final_summary'
]
