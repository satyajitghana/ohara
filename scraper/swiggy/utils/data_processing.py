"""Data processing utilities."""
import json
from typing import List, Dict, Any, Union
from urllib.parse import urlparse, parse_qs


def extract_products_from_data(data: Union[List, Dict]) -> List[Dict[str, Any]]:
    """
    Extract products from various data structures.
    Handles both list format and nested dict format.
    """
    products = []
    
    if isinstance(data, list):
        products = data
    elif isinstance(data, dict):
        # Handle nested structure seen in some files
        nested_products = data.get("data", {}).get("widgets", [{}])[0].get("data", {}).get("products", [])
        if nested_products:
            products = nested_products
    
    return products


def find_products_recursively(data_blob: Union[Dict, List]) -> List[Dict[str, Any]]:
    """Recursively find and extract product data from nested structures."""
    products = []
    
    if isinstance(data_blob, dict):
        # If we find a product list, process it
        if data_blob.get("widgetInfo", {}).get("widgetType") == "PRODUCT_LIST":
            items = data_blob.get("data", [])
            if isinstance(items, list):
                for item in items:
                    if item and isinstance(item, dict) and item.get("variations"):
                        products.append(item)
        # Otherwise, continue searching deeper
        else:
            for key, value in data_blob.items():
                products.extend(find_products_recursively(value))
    elif isinstance(data_blob, list):
        for item in data_blob:
            products.extend(find_products_recursively(item))
    
    return products


def is_combo_item(variation: Dict[str, Any]) -> bool:
    """Check if a variation is a combo item that should be skipped."""
    scm_item_type = variation.get("scm_item_type")
    unit_of_measure = variation.get("unit_of_measure")
    
    # Skip if it's a virtual combo or if unit of measure is combo
    return (scm_item_type == "VIRTUAL_COMBO" or unit_of_measure == "combo")


def extract_variation_details(variation: Dict[str, Any]) -> Dict[str, Any]:
    """Extract and format variation details."""
    price_info = variation.get("price", {})
    
    return {
        "id": variation.get("id"),
        "display_name": variation.get("display_name"),
        # Enhanced price information
        "price": {
            "mrp": price_info.get("mrp"),
            "store_price": price_info.get("store_price"),
            "offer_price": price_info.get("offer_price"),
            "unit_level_price": price_info.get("unit_level_price"),
            "discount_value": price_info.get("discount_value")
        },
        "brand": variation.get("brand"),
        "brand_id": variation.get("brand_id"),
        "category": variation.get("category"),
        "super_category": variation.get("super_category"),
        "sub_category_l3": variation.get("sub_category_l3"),
        "sub_category_l4": variation.get("sub_category_l4"),
        "sub_category_l5": variation.get("sub_category_l5"),
        "product_name_without_brand": variation.get("product_name_without_brand"),
        "images": variation.get("images"),
        "images_v2": variation.get("images_v2"),
        "quantity": variation.get("quantity"),
        "sku_quantity_with_combo": variation.get("sku_quantity_with_combo"),
        "unit_of_measure": variation.get("unit_of_measure"),
        "weight_in_grams": variation.get("weight_in_grams"),
        "volumetric_weight": variation.get("volumetric_weight"),
        "scm_item_type": variation.get("scm_item_type"),
        "filters_tag": variation.get("filters_tag")
    }


def format_product_info(item: Dict[str, Any]) -> Dict[str, Any]:
    """Format product information with variations, filtering out combo items."""
    product_info = {
        "display_name": item.get("display_name"),
        "brand": item.get("brand"),
        "brand_id": item.get("brand_id"),
        "product_id": item.get("product_id"),
        "variations": []
    }
    
    for variation in item.get("variations", []):
        # Skip combo items
        if not is_combo_item(variation):
            variation_details = extract_variation_details(variation)
            product_info["variations"].append(variation_details)
    
    return product_info


def should_include_product(product_info: Dict[str, Any]) -> bool:
    """Check if a product should be included (has at least one non-combo variation)."""
    return len(product_info.get("variations", [])) > 0


def parse_category_link(link: str) -> Dict[str, Any]:
    """Parse category link and extract parameters."""
    try:
        parsed_url = urlparse(link)
        query_params = parse_qs(parsed_url.query)
        
        return {
            "categoryName": query_params.get("categoryName", [None])[0],
            "storeId": query_params.get("storeId", [None])[0],
            "offset": query_params.get("offset", [None])[0],
            "filterName": query_params.get("filterName", [None])[0],
            "taxonomyType": query_params.get("taxonomyType", [None])[0],
        }
    except Exception:
        return {}


def extract_categories_from_response(data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Extract category information from API response."""
    categories = []
    
    # The data is deeply nested, so we need to traverse it carefully
    for card in data.get("data", {}).get("cards", []):
        grid_elements = card.get("card", {}).get("card", {}).get("gridElements", {})
        if grid_elements:
            info_with_style = grid_elements.get("infoWithStyle", {})
            if info_with_style:
                items = info_with_style.get("info", [])
                for item in items:
                    action = item.get("action", {})
                    link = action.get("link")
                    
                    if link and "category-listing" in link:
                        link_params = parse_category_link(link)
                        if link_params:
                            category_info = {
                                "imageId": item.get("imageId"),
                                "description": item.get("description"),
                                "link": link,
                                "link_params": link_params
                            }
                            categories.append(category_info)
    
    return categories
