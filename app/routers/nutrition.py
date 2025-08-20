"""Nutrition and ingredient-based query routes."""
import json
from typing import List, Optional
from fastapi import APIRouter, Depends, Query
from sqlmodel import select, and_, or_, func

from ..database import SessionDep
from ..models import (
    Product, Brand, Ingredient, NutritionFact, 
    ProductPublic, ProductListResponse, VegStatus
)
from ..auth import get_current_active_user


router = APIRouter(prefix="/nutrition", tags=["nutrition"])


@router.get("/allergen-free", response_model=ProductListResponse)
def get_allergen_free_products(
    session: SessionDep,
    exclude_allergens: List[str] = Query(..., description="List of allergens to exclude (e.g., ['Peanut', 'Wheat'])"),
    limit: int = Query(20, le=100, ge=1),
    offset: int = Query(0, ge=0),
    _: Optional[str] = Depends(get_current_active_user)
):
    """Get products that don't contain specified allergens."""
    
    # Get products that don't have the specified allergens
    statement = select(Product, Brand).join(Brand, Product.brand_id == Brand.id)
    
    # Filter out products with specified allergens
    allergen_filters = []
    for allergen in exclude_allergens:
        # Check both the allergens JSON field and ingredients
        allergen_filters.append(
            and_(
                or_(
                    Product.allergens.is_(None),
                    ~Product.allergens.contains(allergen)
                ),
                ~Product.id.in_(
                    select(Ingredient.product_id).where(
                        Ingredient.name.icontains(allergen)
                    )
                )
            )
        )
    
    if allergen_filters:
        statement = statement.where(and_(*allergen_filters))
    
    # Count total results
    count_statement = select(func.count(Product.id)).select_from(statement.subquery())
    total = session.exec(count_statement).one()
    
    # Apply pagination
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


@router.get("/high-protein", response_model=ProductListResponse)
def get_high_protein_products(
    session: SessionDep,
    min_protein_per_100g: float = Query(10.0, description="Minimum protein per 100g"),
    max_carbs_per_100g: Optional[float] = Query(None, description="Maximum carbs per 100g"),
    limit: int = Query(20, le=100, ge=1),
    offset: int = Query(0, ge=0),
    _: Optional[str] = Depends(get_current_active_user)
):
    """Get products with high protein content and optionally low carbs."""
    
    # Get products with protein nutrition facts
    protein_subquery = select(NutritionFact.product_id).where(
        and_(
            NutritionFact.nutrient == "protein",
            NutritionFact.value >= min_protein_per_100g,
            NutritionFact.unit.in_(["g", "gm"])
        )
    )
    
    statement = select(Product, Brand).join(Brand, Product.brand_id == Brand.id).where(
        Product.id.in_(protein_subquery)
    )
    
    # Add carb filter if specified
    if max_carbs_per_100g is not None:
        carb_subquery = select(NutritionFact.product_id).where(
            and_(
                NutritionFact.nutrient.in_(["carbohydrate", "total_carbohydrate"]),
                NutritionFact.value <= max_carbs_per_100g,
                NutritionFact.unit.in_(["g", "gm"])
            )
        )
        statement = statement.where(Product.id.in_(carb_subquery))
    
    # Count total results
    count_statement = select(func.count(Product.id)).select_from(statement.subquery())
    total = session.exec(count_statement).one()
    
    # Apply pagination and sorting by protein content
    statement = statement.order_by(Product.health_rating.desc()).offset(offset).limit(limit)
    
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


@router.get("/low-fat", response_model=ProductListResponse)
def get_low_fat_products(
    session: SessionDep,
    max_fat_per_100g: float = Query(5.0, description="Maximum total fat per 100g"),
    max_saturated_fat_per_100g: Optional[float] = Query(None, description="Maximum saturated fat per 100g"),
    limit: int = Query(20, le=100, ge=1),
    offset: int = Query(0, ge=0),
    _: Optional[str] = Depends(get_current_active_user)
):
    """Get products with low fat content."""
    
    # Get products with low total fat
    fat_subquery = select(NutritionFact.product_id).where(
        and_(
            NutritionFact.nutrient == "total_fat",
            NutritionFact.value <= max_fat_per_100g,
            NutritionFact.unit.in_(["g", "gm"])
        )
    )
    
    statement = select(Product, Brand).join(Brand, Product.brand_id == Brand.id).where(
        Product.id.in_(fat_subquery)
    )
    
    # Add saturated fat filter if specified
    if max_saturated_fat_per_100g is not None:
        sat_fat_subquery = select(NutritionFact.product_id).where(
            and_(
                NutritionFact.nutrient == "saturated_fat",
                NutritionFact.value <= max_saturated_fat_per_100g,
                NutritionFact.unit.in_(["g", "gm"])
            )
        )
        statement = statement.where(Product.id.in_(sat_fat_subquery))
    
    # Count total results
    count_statement = select(func.count(Product.id)).select_from(statement.subquery())
    total = session.exec(count_statement).one()
    
    # Apply pagination
    statement = statement.order_by(Product.health_rating.desc()).offset(offset).limit(limit)
    
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


@router.get("/nutrient/{nutrient_name}")
def get_products_by_nutrient(
    nutrient_name: str,
    session: SessionDep,
    min_value: Optional[float] = Query(None, description="Minimum nutrient value"),
    max_value: Optional[float] = Query(None, description="Maximum nutrient value"),
    unit: Optional[str] = Query(None, description="Unit of measurement"),
    limit: int = Query(20, le=100, ge=1),
    offset: int = Query(0, ge=0),
    _: Optional[str] = Depends(get_current_active_user)
):
    """Get products by specific nutrient content."""
    
    # Build nutrient filter
    nutrient_filters = [NutritionFact.nutrient == nutrient_name]
    
    if min_value is not None:
        nutrient_filters.append(NutritionFact.value >= min_value)
    
    if max_value is not None:
        nutrient_filters.append(NutritionFact.value <= max_value)
    
    if unit:
        nutrient_filters.append(NutritionFact.unit == unit)
    
    # Get products with specified nutrient criteria
    nutrient_subquery = select(NutritionFact.product_id).where(and_(*nutrient_filters))
    
    statement = select(Product, Brand).join(Brand, Product.brand_id == Brand.id).where(
        Product.id.in_(nutrient_subquery)
    )
    
    # Count total results
    count_statement = select(func.count(Product.id)).select_from(statement.subquery())
    total = session.exec(count_statement).one()
    
    # Apply pagination
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


@router.get("/ingredients/avoid")
def get_products_without_ingredients(
    session: SessionDep,
    avoid_ingredients: List[str] = Query(..., description="List of ingredients to avoid"),
    limit: int = Query(20, le=100, ge=1),
    offset: int = Query(0, ge=0),
    _: Optional[str] = Depends(get_current_active_user)
):
    """Get products that don't contain specified ingredients."""
    
    # Get products that don't have the specified ingredients
    statement = select(Product, Brand).join(Brand, Product.brand_id == Brand.id)
    
    # Filter out products with specified ingredients
    for ingredient in avoid_ingredients:
        statement = statement.where(
            ~Product.id.in_(
                select(Ingredient.product_id).where(
                    Ingredient.name.icontains(ingredient)
                )
            )
        )
    
    # Count total results
    count_statement = select(func.count(Product.id)).select_from(statement.subquery())
    total = session.exec(count_statement).one()
    
    # Apply pagination
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
