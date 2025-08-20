"""Brand routes."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import select, func

from ..database import SessionDep
from ..models import Brand, BrandPublic, Product, ProductPublic, ProductListResponse
from ..auth import get_current_active_user


router = APIRouter(prefix="/brands", tags=["brands"])


@router.get("/", response_model=List[BrandPublic])
def get_brands(
    session: SessionDep,
    limit: int = 100,
    offset: int = 0,
    _: Optional[str] = Depends(get_current_active_user)  # Require authentication
):
    """Get all brands with product counts."""
    
    # Get brands with product counts
    statement = select(
        Brand,
        func.count(Product.id).label("product_count")
    ).outerjoin(Product, Brand.id == Product.brand_id).group_by(Brand.id).offset(offset).limit(limit)
    
    results = session.exec(statement).all()
    
    brands = []
    for brand, product_count in results:
        brand_data = BrandPublic.model_validate(brand)
        brand_data.product_count = product_count
        brands.append(brand_data)
    
    return sorted(brands, key=lambda x: x.name)


@router.get("/{brand_id}/products", response_model=ProductListResponse)
def get_brand_products(
    brand_id: int,
    session: SessionDep,
    limit: int = 20,
    offset: int = 0,
    _: Optional[str] = Depends(get_current_active_user)  # Require authentication
):
    """Get all products for a specific brand."""
    
    # Check if brand exists
    brand = session.get(Brand, brand_id)
    if not brand:
        raise HTTPException(status_code=404, detail="Brand not found")
    
    # Get products for this brand
    statement = select(Product, Brand).join(Brand, Product.brand_id == Brand.id).where(
        Product.brand_id == brand_id
    )
    
    # Count total results
    count_statement = select(func.count(Product.id)).where(Product.brand_id == brand_id)
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
