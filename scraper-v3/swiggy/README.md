# Swiggy Scraper v3

A modular Python scraper for Swiggy Instamart category data with proper organization and configuration management.

## Structure

```
scraper-v3/swiggy/
├── config.json              # Configuration file with all settings
├── step1_scrape_home_v2.py  # Script to fetch home API categories
├── step2_scrape_categories.py # Script to scrape category listings
├── utils/                   # Utility modules
│   ├── __init__.py         # Package initialization
│   ├── common.py           # Common utility functions
│   ├── api.py              # API-related utilities
│   └── scraper.py          # Scraping utilities
└── README.md               # This file
```

## Configuration

The `config.json` file contains all the configuration settings:

- **API endpoints and URLs**
- **Store configurations** (default, bangalore_hsr, etc.)
- **Scraping parameters** (concurrency, retries, timeouts)
- **Output directories and filenames**
- **Headers and cookies** for API requests

### Adding New Stores

To scrape data for different stores/locations, add them to the `stores` section in `config.json`:

```json
{
  "stores": {
    "your_store_name": {
      "store_id": "1234567",
      "primary_store_id": "1234567", 
      "secondary_store_id": "7654321",
      "layout_id": "4987",
      "description": "Your Location Description"
    }
  }
}
```

## Usage

### Test Setup (Optional)

To verify that everything is set up correctly:

```bash
cd /home/ubuntu/ohara/scraper-v3/swiggy
python test_setup.py
```

This will test imports, configuration loading, and basic functionality.

### Step 1: Fetch Home API Categories

```bash
cd /home/ubuntu/ohara/scraper-v3/swiggy
python step1_scrape_home_v2.py
```

This will:
- Fetch categories from Swiggy's home API
- Extract category information
- Save raw and processed data to `responses-v3/` directory
- Display a summary of found categories

### Step 2: Scrape Category Listings  

```bash
python step2_scrape_categories.py
```

This will:
- Load categories from step 1 output
- Scrape each category's listing pages with pagination
- Handle rate limiting and retries automatically
- Save all data (HTML, initial state, API responses) for each category

### Step 3: Scrape Filter-Specific Listings

```bash
python step3_scrape_filters.py
```

This will:
- Load categories from step 2 output
- Extract filters from each category's page_0.json
- Scrape each filter with the same pagination logic
- Save filter data in organized subdirectories: `categories/<category_name>/filters/<filter_name>/`

## Output

The scraper creates the following organized output structure:

```
responses-v4/                        # Base output directory (configurable)
├── playwright-swiggy-home.json      # Processed categories from step 1
├── playwright-swiggy-home-raw.json  # Raw API response from step 1
└── categories/                      # All category data organized here
    ├── Category_Name_1/             # One folder per category
    │   ├── Category_Name_1.html           # Main page HTML
    │   ├── Category_Name_1_initial_state.json # Initial page state
    │   ├── Category_Name_1_page_0.json    # Page 0 data (contains filters list)
    │   ├── Category_Name_1_page_1.json    # Page 1 data (if available)
    │   ├── Category_Name_1_api_requests.json  # All API requests made
    │   ├── Category_Name_1_api_responses.json # All API responses captured
    │   └── filters/                       # Filter-specific data (from step 3)
    │       ├── Filter_Name_1/             # One folder per filter
    │       │   ├── Filter_Name_1.html           # Filter page HTML
    │       │   ├── Filter_Name_1_initial_state.json # Filter page state
    │       │   ├── Filter_Name_1_page_0.json    # Filter page 0 data
    │       │   ├── Filter_Name_1_page_1.json    # Filter page 1 data (if available)
    │       │   ├── Filter_Name_1_api_requests.json  # Filter API requests
    │       │   └── Filter_Name_1_api_responses.json # Filter API responses
    │       └── Filter_Name_2/
    │           └── ...
    ├── Category_Name_2/
    │   └── ...
    └── Category_Name_N/
        └── ...
```

## Key Features

### Organized Code Structure
- Modular design with separate utility modules
- Clean separation between API handling and scraping logic
- Centralized configuration management
- Organized output structure with categories in dedicated subdirectories

### Robust Error Handling
- Automatic retries for rate limiting
- Category-level retry logic for API errors
- Graceful handling of missing data

### Configurable Parallelism
- Configurable number of concurrent categories
- Batch processing with delays between batches
- Prevents overwhelming the target server

### Complete Data Capture
- Saves HTML content for debugging
- Captures all API requests and responses
- Preserves initial page state
- Handles pagination automatically

## Configuration Options

Key configuration parameters in `config.json`:

```json
{
  "scraping": {
    "max_concurrent_categories": 20,    # Parallel categories to scrape
    "max_concurrent_filters": 5,       # Parallel filters per category
    "max_retries": 5,                   # Retries for rate limits
    "max_category_retries": 5,          # Retries for category failures
    "max_filter_retries": 3,            # Retries for filter failures
    "max_scroll_loops": 20,             # Max pagination loops
    "retry_delay_seconds": 3,           # Delay between retries
    "category_retry_delay_seconds": 5,  # Delay between category retries
    "filter_retry_delay_seconds": 3,    # Delay between filter retries
    "batch_delay_seconds": 5,           # Delay between category batches
    "filter_batch_delay_seconds": 2     # Delay between filter batches
  }
}
```

## Requirements

- Python 3.7+
- playwright
- requests
- beautifulsoup4

Install with:
```bash
pip install playwright requests beautifulsoup4
playwright install
```

## Troubleshooting

### Rate Limiting
The scraper handles rate limiting automatically with retries and delays. If you encounter persistent rate limiting:
- Reduce `max_concurrent_categories` in config
- Increase delay values in config
- Check if your cookies/headers need updating

### Missing Categories
If step1 doesn't find categories:
- Check if the store configuration is correct
- Verify headers and cookies are up to date
- Check if the API endpoints have changed

### Scraping Failures
If step2 fails for specific categories:
- Check the individual category HTML files for debugging
- Look at the API responses for error messages
- Verify the category deeplinks are still valid

## Store ID Discovery

To find store IDs for different locations:
1. Visit https://www.swiggy.com/instamart in your browser
2. Set your delivery location
3. Open browser developer tools (F12)
4. Look for API calls to `/api/instamart/home/v2`
5. Check the `storeId` parameter in the URL
6. Add the new store configuration to `config.json`
