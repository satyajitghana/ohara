"""Product routes."""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, func, or_, and_

from ..database import SessionDep
from ..models import (
    Product, Brand, ProductPublic, ProductDetail, ProductListResponse,
    ProductSearchParams, VegStatus, ProcessingLevel
)
from ..auth import get_current_active_user


router = APIRouter(prefix="/products", tags=["products"])


@router.get("/search", response_model=ProductListResponse)
def search_products(
    session: SessionDep,
    query: Optional[str] = Query(None, description="Search query for product name or display name"),
    brand_name: Optional[str] = Query(None, description="Filter by brand name"),
    category: Optional[str] = Query(None, description="Filter by category"),
    super_category: Optional[str] = Query(None, description="Filter by super category"),
    veg_status: Optional[VegStatus] = Query(None, description="Filter by vegetarian status"),
    min_health_rating: Optional[int] = Query(None, ge=0, le=100, description="Minimum health rating"),
    max_health_rating: Optional[int] = Query(None, ge=0, le=100, description="Maximum health rating"),
    processing_level: Optional[ProcessingLevel] = Query(None, description="Filter by processing level"),
    sort_by: str = Query("name", regex="^(name|display_name|offer_price|health_rating|created_at)$", description="Sort by field"),
    sort_order: str = Query("asc", regex="^(asc|desc)$", description="Sort order"),
    limit: int = Query(20, le=100, ge=1, description="Number of results to return"),
    offset: int = Query(0, ge=0, description="Number of results to skip"),
    _: Optional[str] = Depends(get_current_active_user)  # Require authentication
):
    """Search products with filters and sorting."""
    
    # Build the query
    statement = select(Product, Brand).join(Brand, Product.brand_id == Brand.id)
    
    # Apply filters
    filters = []
    
    if query:
        filters.append(
            or_(
                Product.name.icontains(query),
                Product.display_name.icontains(query),
                Brand.name.icontains(query)
            )
        )
    
    if brand_name:
        filters.append(Brand.name.icontains(brand_name))
    
    if category:
        filters.append(Product.category.icontains(category))
    
    if super_category:
        filters.append(Product.super_category.icontains(super_category))
    
    if veg_status:
        filters.append(Product.veg_status == veg_status)
    
    if min_health_rating is not None:
        filters.append(Product.health_rating >= min_health_rating)
    
    if max_health_rating is not None:
        filters.append(Product.health_rating <= max_health_rating)
    
    if processing_level:
        filters.append(Product.processing_level == processing_level)
    
    if filters:
        statement = statement.where(and_(*filters))
    
    # Count total results
    count_statement = select(func.count(Product.id)).select_from(statement.subquery())
    total = session.exec(count_statement).one()
    
    # Apply sorting
    sort_field = getattr(Product, sort_by)
    if sort_order == "desc":
        statement = statement.order_by(sort_field.desc())
    else:
        statement = statement.order_by(sort_field.asc())
    
    # Apply pagination
    statement = statement.offset(offset).limit(limit)
    
    # Execute query
    results = session.exec(statement).all()
    
    # Transform results
    products = []
    for product, brand in results:
        product_data = ProductPublic.model_validate(product)
        product_data.brand = brand
        products.append(product_data)
    
    return ProductListResponse(
        products=products,
        total=total,
        limit=limit,
        offset=offset
    )


@router.get("/barcode/{barcode}", response_model=ProductDetail)
def get_product_by_barcode(
    barcode: str,
    session: SessionDep,
    _: Optional[str] = Depends(get_current_active_user)  # Require authentication
):
    """Get product by barcode."""
    statement = select(Product, Brand).join(Brand, Product.brand_id == Brand.id).where(Product.barcode == barcode)
    result = session.exec(statement).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product, brand = result
    
    # Get detailed product with nutrition and ingredients
    product_detail = ProductDetail.model_validate(product)
    product_detail.brand = brand
    
    # Load nutrition facts and ingredients
    from ..models import NutritionFact, Ingredient
    
    nutrition_statement = select(NutritionFact).where(NutritionFact.product_id == product.id)
    nutrition_facts = session.exec(nutrition_statement).all()
    product_detail.nutrition_facts = nutrition_facts
    
    ingredients_statement = select(Ingredient).where(Ingredient.product_id == product.id)
    ingredients = session.exec(ingredients_statement).all()
    product_detail.ingredients = ingredients
    
    return product_detail


@router.get("/{product_id}", response_model=ProductDetail)
def get_product_detail(
    product_id: int,
    session: SessionDep,
    _: Optional[str] = Depends(get_current_active_user)  # Require authentication
):
    """Get detailed product information by ID."""
    statement = select(Product, Brand).join(Brand, Product.brand_id == Brand.id).where(Product.id == product_id)
    result = session.exec(statement).first()
    
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product, brand = result
    
    # Get detailed product with nutrition and ingredients
    product_detail = ProductDetail.model_validate(product)
    product_detail.brand = brand
    
    # Load nutrition facts and ingredients
    from ..models import NutritionFact, Ingredient
    
    nutrition_statement = select(NutritionFact).where(NutritionFact.product_id == product.id)
    nutrition_facts = session.exec(nutrition_statement).all()
    product_detail.nutrition_facts = nutrition_facts
    
    ingredients_statement = select(Ingredient).where(Ingredient.product_id == product.id)
    ingredients = session.exec(ingredients_statement).all()
    product_detail.ingredients = ingredients
    
    return product_detail
