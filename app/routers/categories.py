"""Categories routes."""
from typing import List, Optional, Dict
from fastapi import APIRouter, Depends
from sqlmodel import select, func, distinct

from ..database import SessionDep
from ..models import Product, CategoryInfo
from ..auth import get_current_active_user


router = APIRouter(prefix="/categories", tags=["categories"])


@router.get("/", response_model=List[CategoryInfo])
def get_categories(
    session: SessionDep,
    _: Optional[str] = Depends(get_current_active_user)  # Require authentication
):
    """Get all categories with product counts."""
    
    # Get categories with counts
    statement = select(
        Product.category,
        func.count(Product.id).label("count")
    ).where(
        Product.category.is_not(None)
    ).group_by(Product.category)
    
    results = session.exec(statement).all()
    
    categories = []
    for category, count in results:
        # Get super categories for this category
        super_cat_statement = select(distinct(Product.super_category)).where(
            Product.category == category,
            Product.super_category.is_not(None)
        )
        super_categories = [sc for sc in session.exec(super_cat_statement).all()]
        
        categories.append(CategoryInfo(
            name=category,
            count=count,
            super_categories=super_categories
        ))
    
    return sorted(categories, key=lambda x: x.name)


@router.get("/super", response_model=List[CategoryInfo])
def get_super_categories(
    session: SessionDep,
    _: Optional[str] = Depends(get_current_active_user)  # Require authentication
):
    """Get all super categories with product counts."""
    
    # Get super categories with counts
    statement = select(
        Product.super_category,
        func.count(Product.id).label("count")
    ).where(
        Product.super_category.is_not(None)
    ).group_by(Product.super_category)
    
    results = session.exec(statement).all()
    
    super_categories = []
    for super_category, count in results:
        super_categories.append(CategoryInfo(
            name=super_category,
            count=count
        ))
    
    return sorted(super_categories, key=lambda x: x.name)


@router.get("/{category_name}/products")
def get_products_by_category(
    category_name: str,
    session: SessionDep,
    super_category: Optional[str] = None,
    limit: int = 20,
    offset: int = 0,
    _: Optional[str] = Depends(get_current_active_user)  # Require authentication
):
    """Get products in a specific category, optionally grouped by super category."""
    
    from ..models import Brand, ProductPublic, ProductListResponse
    
    # Build the query
    statement = select(Product, Brand).join(Brand, Product.brand_id == Brand.id).where(
        Product.category == category_name
    )
    
    if super_category:
        statement = statement.where(Product.super_category == super_category)
    
    # Count total results
    count_statement = select(func.count(Product.id)).select_from(statement.subquery())
    total = session.exec(count_statement).one()
    
    # Apply pagination and sorting
    statement = statement.order_by(Product.display_name.asc()).offset(offset).limit(limit)
    
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
