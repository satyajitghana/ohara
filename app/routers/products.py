"""Product routes."""
import json
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import select, and_, or_, func
from sqlalchemy import desc, asc

from ..database import SessionDep
from ..models import (
    Product, ProductDetail, ProductListItem, ProductSearchResponse, 
    ProductSearchFilter, Brand, SuperCategory, Category, 
    BrandResponse, SuperCategoryResponse, CategoryResponse, SuperCategoryDetail,
    VegStatus, ProcessingLevel, DataSource, ProductImage,
    NutritionFact, Ingredient, NutritionFactResponse, IngredientResponse
)
from ..auth import get_current_active_user

router = APIRouter(prefix="/products", tags=["products"])


@router.get("/super-categories", response_model=List[SuperCategoryResponse])
def get_super_categories(
    session: SessionDep,
    _: str = Depends(get_current_active_user)
) -> List[SuperCategoryResponse]:
    """Get all super categories with product counts for homepage display."""
    # Query super categories with product counts
    statement = (
        select(SuperCategory, func.count(Product.id).label("product_count"))
        .outerjoin(Product, SuperCategory.id == Product.super_category_id)
        .group_by(SuperCategory.id)
        .order_by(SuperCategory.name)
    )
    
    results = session.exec(statement).all()
    
    super_categories = []
    for super_category, product_count in results:
        super_categories.append(SuperCategoryResponse(
            id=super_category.id,
            name=super_category.name,
            image_filename=super_category.image_filename,
            taxonomy_type=super_category.taxonomy_type,
            product_count=product_count
        ))
    
    return super_categories


@router.get("/super-categories/{super_category_id}", response_model=SuperCategoryDetail)
def get_super_category_with_categories(
    super_category_id: int,
    session: SessionDep,
    _: str = Depends(get_current_active_user)
) -> SuperCategoryDetail:
    """Get super category details with all its categories for sidebar display."""
    # Get super category
    super_category = session.get(SuperCategory, super_category_id)
    if not super_category:
        raise HTTPException(status_code=404, detail="Super category not found")
    
    # Get super category product count
    super_category_count_statement = (
        select(func.count(Product.id))
        .where(Product.super_category_id == super_category_id)
    )
    super_category_product_count = session.exec(super_category_count_statement).one()
    
    # Get categories with product counts
    categories_statement = (
        select(Category, func.count(Product.id).label("product_count"))
        .outerjoin(Product, Category.id == Product.category_id)
        .where(Category.super_category_id == super_category_id)
        .group_by(Category.id)
        .order_by(Category.name)
    )
    
    category_results = session.exec(categories_statement).all()
    
    categories = []
    for category, product_count in category_results:
        categories.append(CategoryResponse(
            id=category.id,
            name=category.name,
            image_filename=category.image_filename,
            product_count=product_count,
            age_consent_required=category.age_consent_required
        ))
    
    return SuperCategoryDetail(
        id=super_category.id,
        name=super_category.name,
        image_filename=super_category.image_filename,
        taxonomy_type=super_category.taxonomy_type,
        product_count=super_category_product_count,
        categories=categories
    )


@router.get("/super-categories/{super_category_id}/products", response_model=ProductSearchResponse)
def get_super_category_products(
    super_category_id: int,
    session: SessionDep,
    _: str = Depends(get_current_active_user),
    # Optional category filter
    category_id: Optional[int] = Query(None, description="Filter by specific category within super category"),
    # Search and filters
    query: Optional[str] = Query(None, description="Search query for product name"),
    brand_name: Optional[str] = Query(None, description="Filter by brand name"),
    veg_status: Optional[VegStatus] = Query(None, description="Filter by vegetarian status"),
    min_health_rating: Optional[int] = Query(None, description="Minimum health rating (0-100)", ge=0, le=100),
    max_health_rating: Optional[int] = Query(None, description="Maximum health rating (0-100)", ge=0, le=100),
    processing_level: Optional[ProcessingLevel] = Query(None, description="Filter by processing level"),
    min_price: Optional[float] = Query(None, description="Minimum price", ge=0),
    max_price: Optional[float] = Query(None, description="Maximum price", ge=0),
    # Sorting and pagination
    sort_by: str = Query("name", description="Sort by field", regex="^(name|price|health_rating|created_at)$"),
    sort_order: str = Query("asc", description="Sort order", regex="^(asc|desc)$"),
    limit: int = Query(20, description="Number of products to return", le=100, ge=1),
    offset: int = Query(0, description="Number of products to skip", ge=0)
) -> ProductSearchResponse:
    """Get products from a specific super category with optional category filtering."""
    
    # Verify super category exists
    super_category = session.get(SuperCategory, super_category_id)
    if not super_category:
        raise HTTPException(status_code=404, detail="Super category not found")
    
    # Verify category exists if provided and belongs to super category
    if category_id:
        category = session.get(Category, category_id)
        if not category or category.super_category_id != super_category_id:
            raise HTTPException(status_code=404, detail="Category not found in this super category")
    
    # Build the base query with joins
    base_query = (
        select(Product, Brand, SuperCategory, Category)
        .join(Brand, Product.brand_id == Brand.id)
        .join(SuperCategory, Product.super_category_id == SuperCategory.id)
        .join(Category, Product.category_id == Category.id)
        .where(Product.super_category_id == super_category_id)
    )
    
    # Build WHERE conditions
    where_conditions = [Product.super_category_id == super_category_id]
    
    # Category filter
    if category_id:
        where_conditions.append(Product.category_id == category_id)
    
    # Text search - search in product name, display name, and brand name
    if query:
        search_term = f"%{query}%"
        where_conditions.append(
            or_(
                Product.name.ilike(search_term),
                Product.display_name.ilike(search_term),
                Brand.name.ilike(search_term)
            )
        )
    
    # Brand filter
    if brand_name:
        where_conditions.append(Brand.name.ilike(f"%{brand_name}%"))
    
    # Health filters
    if veg_status:
        where_conditions.append(Product.veg_status == veg_status)
    
    if min_health_rating is not None:
        where_conditions.append(Product.health_rating >= min_health_rating)
    
    if max_health_rating is not None:
        where_conditions.append(Product.health_rating <= max_health_rating)
    
    if processing_level:
        where_conditions.append(Product.processing_level == processing_level)
    
    # Price filters (using offer_price first, then store_price, then mrp)
    if min_price is not None or max_price is not None:
        price_field = func.coalesce(Product.offer_price, Product.store_price, Product.mrp)
        if min_price is not None:
            where_conditions.append(price_field >= min_price)
        if max_price is not None:
            where_conditions.append(price_field <= max_price)
    
    # Apply WHERE conditions
    if where_conditions:
        base_query = base_query.where(and_(*where_conditions))
    
    # Get total count
    count_query = select(func.count(Product.id))
    if where_conditions:
        # The join is necessary because the where_conditions might reference Brand.name
        count_query = (
            select(func.count(Product.id))
            .select_from(Product)
            .join(Brand, Product.brand_id == Brand.id)
            .where(and_(*where_conditions))
        )
    
    total = session.exec(count_query).one()
    
    # Apply sorting
    sort_field_map = {
        "name": Product.name,
        "price": func.coalesce(Product.offer_price, Product.store_price, Product.mrp),
        "health_rating": Product.health_rating,
        "created_at": Product.created_at
    }
    
    sort_field = sort_field_map.get(sort_by, Product.name)
    order_func = desc if sort_order == "desc" else asc
    base_query = base_query.order_by(order_func(sort_field))
    
    # Apply pagination
    base_query = base_query.offset(offset).limit(limit)
    
    # Execute query
    results = session.exec(base_query).all()
    
    # Convert to response models
    products = []
    for product, brand, super_category, category in results:
        # Get primary image
        image_statement = select(ProductImage).where(
            and_(ProductImage.product_id == product.id, ProductImage.is_primary == True)
        )
        primary_image_result = session.exec(image_statement).first()
        primary_image = primary_image_result.filename if primary_image_result else None
        
        # If no primary image, get the first image
        if not primary_image:
            first_image_statement = select(ProductImage).where(
                ProductImage.product_id == product.id
            ).order_by(ProductImage.order_index).limit(1)
            first_image_result = session.exec(first_image_statement).first()
            primary_image = first_image_result.filename if first_image_result else None
        
        brand_response = BrandResponse(id=brand.id, name=brand.name)
        
        product_item = ProductListItem(
            id=product.id,
            name=product.name,
            display_name=product.display_name,
            brand=brand_response,
            veg_status=product.veg_status,
            health_rating=product.health_rating,
            processing_level=product.processing_level,
            mrp=product.mrp,
            store_price=product.store_price,
            offer_price=product.offer_price,
            discount_value=product.discount_value,
            quantity=product.quantity,
            weight_in_grams=product.weight_in_grams,
            unit_of_measure=product.unit_of_measure,
            sub_category_l3=product.sub_category_l3,
            sub_category_l4=product.sub_category_l4,
            sub_category_l5=product.sub_category_l5,
            primary_image=primary_image
        )
        products.append(product_item)
    
    # Create filter object for response
    filters_applied = ProductSearchFilter(
        query=query,
        brand_name=brand_name,
        super_category_id=super_category_id,
        category_id=category_id,
        veg_status=veg_status,
        min_health_rating=min_health_rating,
        max_health_rating=max_health_rating,
        processing_level=processing_level,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset
    )
    
    return ProductSearchResponse(
        products=products,
        total=total,
        limit=limit,
        offset=offset,
        filters_applied=filters_applied
    )


@router.get("/barcode/{barcode}", response_model=ProductDetail)
def get_product_by_barcode(
    barcode: str,
    session: SessionDep,
    _: str = Depends(get_current_active_user)
) -> ProductDetail:
    """Get product by barcode scan."""
    # Query product with all relationships
    statement = (
        select(Product, Brand, SuperCategory, Category)
        .join(Brand, Product.brand_id == Brand.id)
        .join(SuperCategory, Product.super_category_id == SuperCategory.id)
        .join(Category, Product.category_id == Category.id)
        .where(Product.barcode == barcode)
    )
    
    result = session.exec(statement).first()
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product, brand, super_category, category = result
    
    # Get images
    image_statement = select(ProductImage).where(ProductImage.product_id == product.id).order_by(ProductImage.order_index)
    images = session.exec(image_statement).all()
    image_filenames = [img.filename for img in images]
    primary_image = None
    for img in images:
        if img.is_primary:
            primary_image = img.filename
            break
    if not primary_image and image_filenames:
        primary_image = image_filenames[0]
    
    # Get nutrition facts
    nutrition_statement = select(NutritionFact).where(NutritionFact.product_id == product.id)
    nutrition_facts = session.exec(nutrition_statement).all()
    
    # Get ingredients
    ingredient_statement = select(Ingredient).where(Ingredient.product_id == product.id).order_by(Ingredient.order_index)
    ingredients = session.exec(ingredient_statement).all()
    
    # Parse JSON fields safely
    def safe_json_parse(json_str: Optional[str]) -> List[str]:
        if not json_str:
            return []
        try:
            result = json.loads(json_str)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    # Convert to response models
    brand_response = BrandResponse(id=brand.id, name=brand.name)
    super_category_response = SuperCategoryResponse(
        id=super_category.id, 
        name=super_category.name,
        image_filename=super_category.image_filename,
        taxonomy_type=super_category.taxonomy_type
    )
    category_response = CategoryResponse(
        id=category.id,
        name=category.name,
        image_filename=category.image_filename,
        product_count=category.product_count,
        age_consent_required=category.age_consent_required
    )
    
    nutrition_responses = [
        NutritionFactResponse(
            id=nf.id,
            nutrient=nf.nutrient,
            value=nf.value,
            unit=nf.unit,
            rda_percentage=nf.rda_percentage
        )
        for nf in nutrition_facts
    ]
    
    ingredient_responses = [
        IngredientResponse(
            id=ing.id,
            name=ing.name,
            percentage=ing.percentage,
            ins_numbers=safe_json_parse(ing.ins_numbers),
            additives=safe_json_parse(ing.additives),
            is_alarming=ing.is_alarming,
            alarming_reason=ing.alarming_reason
        )
        for ing in ingredients
    ]
    
    return ProductDetail(
        id=product.id,
        name=product.name,
        display_name=product.display_name,
        brand=brand_response,
        primary_source=product.primary_source,
        primary_external_id=product.primary_external_id,
        primary_external_variation_id=product.primary_external_variation_id,
        super_category=super_category_response,
        category=category_response,
        sub_category_l3=product.sub_category_l3,
        sub_category_l4=product.sub_category_l4,
        sub_category_l5=product.sub_category_l5,
        veg_status=product.veg_status,
        health_rating=product.health_rating,
        processing_level=product.processing_level,
        mrp=product.mrp,
        store_price=product.store_price,
        offer_price=product.offer_price,
        discount_value=product.discount_value,
        unit_level_price=product.unit_level_price,
        quantity=product.quantity,
        weight_in_grams=product.weight_in_grams,
        unit_of_measure=product.unit_of_measure,
        volumetric_weight=product.volumetric_weight,
        sku_quantity_with_combo=product.sku_quantity_with_combo,
        primary_image=primary_image,
        images=image_filenames,
        barcode=product.barcode,
        country_of_origin=product.country_of_origin,
        net_quantity_value=product.net_quantity_value,
        net_quantity_unit=product.net_quantity_unit,
        nutrition_serving_value=product.nutrition_serving_value,
        nutrition_serving_unit=product.nutrition_serving_unit,
        approx_serves_per_pack=product.approx_serves_per_pack,
        ingredients_string=product.ingredients_string,
        storage_instructions=product.storage_instructions,
        cooking_instructions=product.cooking_instructions,
        ingredients=ingredient_responses,
        nutrition_facts=nutrition_responses,
        allergens=safe_json_parse(product.allergens),
        certifications=safe_json_parse(product.certifications),
        positive_health_aspects=safe_json_parse(product.positive_health_aspects),
        negative_health_aspects=safe_json_parse(product.negative_health_aspects),
        tags=[],  # You can add tags logic here if needed
        created_at=product.created_at,
        updated_at=product.updated_at
    )


@router.get("/search", response_model=ProductSearchResponse)
def search_products(
    session: SessionDep,
    _: str = Depends(get_current_active_user),
    # Search parameters
    query: Optional[str] = Query(None, description="Search query for product name"),
    brand_name: Optional[str] = Query(None, description="Filter by brand name"),
    barcode: Optional[str] = Query(None, description="Search by barcode"),
    super_category_id: Optional[int] = Query(None, description="Filter by super category ID"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    sub_category_l3: Optional[str] = Query(None, description="Filter by sub category L3"),
    sub_category_l4: Optional[str] = Query(None, description="Filter by sub category L4"),
    sub_category_l5: Optional[str] = Query(None, description="Filter by sub category L5"),
    veg_status: Optional[VegStatus] = Query(None, description="Filter by vegetarian status"),
    min_health_rating: Optional[int] = Query(None, description="Minimum health rating (0-100)", ge=0, le=100),
    max_health_rating: Optional[int] = Query(None, description="Maximum health rating (0-100)", ge=0, le=100),
    processing_level: Optional[ProcessingLevel] = Query(None, description="Filter by processing level"),
    min_price: Optional[float] = Query(None, description="Minimum price", ge=0),
    max_price: Optional[float] = Query(None, description="Maximum price", ge=0),
    # Sorting and pagination
    sort_by: str = Query("name", description="Sort by field", regex="^(name|price|health_rating|created_at)$"),
    sort_order: str = Query("asc", description="Sort order", regex="^(asc|desc)$"),
    limit: int = Query(20, description="Number of products to return", le=100, ge=1),
    offset: int = Query(0, description="Number of products to skip", ge=0)
) -> ProductSearchResponse:
    """Search products with filters, sorting, and pagination."""
    
    # Build the base query with joins
    base_query = (
        select(Product, Brand, SuperCategory, Category)
        .join(Brand, Product.brand_id == Brand.id)
        .join(SuperCategory, Product.super_category_id == SuperCategory.id)
        .join(Category, Product.category_id == Category.id)
    )
    
    # Build WHERE conditions
    where_conditions = []
    
    # Text search - search in product name, display name, and brand name
    if query:
        search_term = f"%{query}%"
        where_conditions.append(
            or_(
                Product.name.ilike(search_term),
                Product.display_name.ilike(search_term),
                Brand.name.ilike(search_term)
            )
        )
    
    # Brand filter
    if brand_name:
        where_conditions.append(Brand.name.ilike(f"%{brand_name}%"))
    
    # Barcode search
    if barcode:
        where_conditions.append(Product.barcode == barcode)
    
    # Category filters
    if super_category_id:
        where_conditions.append(Product.super_category_id == super_category_id)
    
    if category_id:
        where_conditions.append(Product.category_id == category_id)
    
    if sub_category_l3:
        where_conditions.append(Product.sub_category_l3.ilike(f"%{sub_category_l3}%"))
    
    if sub_category_l4:
        where_conditions.append(Product.sub_category_l4.ilike(f"%{sub_category_l4}%"))
    
    if sub_category_l5:
        where_conditions.append(Product.sub_category_l5.ilike(f"%{sub_category_l5}%"))
    
    # Health filters
    if veg_status:
        where_conditions.append(Product.veg_status == veg_status)
    
    if min_health_rating is not None:
        where_conditions.append(Product.health_rating >= min_health_rating)
    
    if max_health_rating is not None:
        where_conditions.append(Product.health_rating <= max_health_rating)
    
    if processing_level:
        where_conditions.append(Product.processing_level == processing_level)
    
    # Price filters (using offer_price first, then store_price, then mrp)
    if min_price is not None or max_price is not None:
        price_field = func.coalesce(Product.offer_price, Product.store_price, Product.mrp)
        if min_price is not None:
            where_conditions.append(price_field >= min_price)
        if max_price is not None:
            where_conditions.append(price_field <= max_price)
    
    # Apply WHERE conditions
    if where_conditions:
        base_query = base_query.where(and_(*where_conditions))
    
    # Get total count
    count_query = select(func.count(Product.id))
    if where_conditions:
        # The join is necessary because the where_conditions might reference Brand.name
        count_query = (
            select(func.count(Product.id))
            .select_from(Product)
            .join(Brand, Product.brand_id == Brand.id)
            .where(and_(*where_conditions))
        )
    
    total = session.exec(count_query).one()
    
    # Apply sorting
    sort_field_map = {
        "name": Product.name,
        "price": func.coalesce(Product.offer_price, Product.store_price, Product.mrp),
        "health_rating": Product.health_rating,
        "created_at": Product.created_at
    }
    
    sort_field = sort_field_map.get(sort_by, Product.name)
    order_func = desc if sort_order == "desc" else asc
    base_query = base_query.order_by(order_func(sort_field))
    
    # Apply pagination
    base_query = base_query.offset(offset).limit(limit)
    
    # Execute query
    results = session.exec(base_query).all()
    
    # Convert to response models
    products = []
    for product, brand, super_category, category in results:
        # Get primary image
        image_statement = select(ProductImage).where(
            and_(ProductImage.product_id == product.id, ProductImage.is_primary == True)
        )
        primary_image_result = session.exec(image_statement).first()
        primary_image = primary_image_result.filename if primary_image_result else None
        
        # If no primary image, get the first image
        if not primary_image:
            first_image_statement = select(ProductImage).where(
                ProductImage.product_id == product.id
            ).order_by(ProductImage.order_index).limit(1)
            first_image_result = session.exec(first_image_statement).first()
            primary_image = first_image_result.filename if first_image_result else None
        
        brand_response = BrandResponse(id=brand.id, name=brand.name)
        
        product_item = ProductListItem(
            id=product.id,
            name=product.name,
            display_name=product.display_name,
            brand=brand_response,
            veg_status=product.veg_status,
            health_rating=product.health_rating,
            processing_level=product.processing_level,
            mrp=product.mrp,
            store_price=product.store_price,
            offer_price=product.offer_price,
            discount_value=product.discount_value,
            quantity=product.quantity,
            weight_in_grams=product.weight_in_grams,
            unit_of_measure=product.unit_of_measure,
            sub_category_l3=product.sub_category_l3,
            sub_category_l4=product.sub_category_l4,
            sub_category_l5=product.sub_category_l5,
            primary_image=primary_image
        )
        products.append(product_item)
    
    # Create filter object for response
    filters_applied = ProductSearchFilter(
        query=query,
        brand_name=brand_name,
        barcode=barcode,
        super_category_id=super_category_id,
        category_id=category_id,
        sub_category_l3=sub_category_l3,
        sub_category_l4=sub_category_l4,
        sub_category_l5=sub_category_l5,
        veg_status=veg_status,
        min_health_rating=min_health_rating,
        max_health_rating=max_health_rating,
        processing_level=processing_level,
        min_price=min_price,
        max_price=max_price,
        sort_by=sort_by,
        sort_order=sort_order,
        limit=limit,
        offset=offset
    )
    
    return ProductSearchResponse(
        products=products,
        total=total,
        limit=limit,
        offset=offset,
        filters_applied=filters_applied
    )


@router.get("/{product_id}", response_model=ProductDetail)
def get_product_detail(
    product_id: int,
    session: SessionDep,
    _: str = Depends(get_current_active_user)
) -> ProductDetail:
    """Get complete product details by ID."""
    # Query product with all relationships
    statement = (
        select(Product, Brand, SuperCategory, Category)
        .join(Brand, Product.brand_id == Brand.id)
        .join(SuperCategory, Product.super_category_id == SuperCategory.id)
        .join(Category, Product.category_id == Category.id)
        .where(Product.id == product_id)
    )
    
    result = session.exec(statement).first()
    if not result:
        raise HTTPException(status_code=404, detail="Product not found")
    
    product, brand, super_category, category = result
    
    # Get images
    image_statement = select(ProductImage).where(ProductImage.product_id == product.id).order_by(ProductImage.order_index)
    images = session.exec(image_statement).all()
    image_filenames = [img.filename for img in images]
    primary_image = None
    for img in images:
        if img.is_primary:
            primary_image = img.filename
            break
    if not primary_image and image_filenames:
        primary_image = image_filenames[0]
    
    # Get nutrition facts
    nutrition_statement = select(NutritionFact).where(NutritionFact.product_id == product.id)
    nutrition_facts = session.exec(nutrition_statement).all()
    
    # Get ingredients
    ingredient_statement = select(Ingredient).where(Ingredient.product_id == product.id).order_by(Ingredient.order_index)
    ingredients = session.exec(ingredient_statement).all()
    
    # Parse JSON fields safely
    def safe_json_parse(json_str: Optional[str]) -> List[str]:
        if not json_str:
            return []
        try:
            result = json.loads(json_str)
            return result if isinstance(result, list) else []
        except (json.JSONDecodeError, TypeError):
            return []
    
    # Convert to response models
    brand_response = BrandResponse(id=brand.id, name=brand.name)
    super_category_response = SuperCategoryResponse(
        id=super_category.id, 
        name=super_category.name,
        image_filename=super_category.image_filename,
        taxonomy_type=super_category.taxonomy_type
    )
    category_response = CategoryResponse(
        id=category.id,
        name=category.name,
        image_filename=category.image_filename,
        product_count=category.product_count,
        age_consent_required=category.age_consent_required
    )
    
    nutrition_responses = [
        NutritionFactResponse(
            id=nf.id,
            nutrient=nf.nutrient,
            value=nf.value,
            unit=nf.unit,
            rda_percentage=nf.rda_percentage
        )
        for nf in nutrition_facts
    ]
    
    ingredient_responses = [
        IngredientResponse(
            id=ing.id,
            name=ing.name,
            percentage=ing.percentage,
            ins_numbers=safe_json_parse(ing.ins_numbers),
            additives=safe_json_parse(ing.additives),
            is_alarming=ing.is_alarming,
            alarming_reason=ing.alarming_reason
        )
        for ing in ingredients
    ]
    
    return ProductDetail(
        id=product.id,
        name=product.name,
        display_name=product.display_name,
        brand=brand_response,
        primary_source=product.primary_source,
        primary_external_id=product.primary_external_id,
        primary_external_variation_id=product.primary_external_variation_id,
        super_category=super_category_response,
        category=category_response,
        sub_category_l3=product.sub_category_l3,
        sub_category_l4=product.sub_category_l4,
        sub_category_l5=product.sub_category_l5,
        veg_status=product.veg_status,
        health_rating=product.health_rating,
        processing_level=product.processing_level,
        mrp=product.mrp,
        store_price=product.store_price,
        offer_price=product.offer_price,
        discount_value=product.discount_value,
        unit_level_price=product.unit_level_price,
        quantity=product.quantity,
        weight_in_grams=product.weight_in_grams,
        unit_of_measure=product.unit_of_measure,
        volumetric_weight=product.volumetric_weight,
        sku_quantity_with_combo=product.sku_quantity_with_combo,
        primary_image=primary_image,
        images=image_filenames,
        barcode=product.barcode,
        country_of_origin=product.country_of_origin,
        net_quantity_value=product.net_quantity_value,
        net_quantity_unit=product.net_quantity_unit,
        nutrition_serving_value=product.nutrition_serving_value,
        nutrition_serving_unit=product.nutrition_serving_unit,
        approx_serves_per_pack=product.approx_serves_per_pack,
        ingredients_string=product.ingredients_string,
        storage_instructions=product.storage_instructions,
        cooking_instructions=product.cooking_instructions,
        ingredients=ingredient_responses,
        nutrition_facts=nutrition_responses,
        allergens=safe_json_parse(product.allergens),
        certifications=safe_json_parse(product.certifications),
        positive_health_aspects=safe_json_parse(product.positive_health_aspects),
        negative_health_aspects=safe_json_parse(product.negative_health_aspects),
        tags=[],  # You can add tags logic here if needed
        created_at=product.created_at,
        updated_at=product.updated_at
    )
