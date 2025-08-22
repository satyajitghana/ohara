"""Database models using SQLModel."""
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import UniqueConstraint
from enum import Enum


class DataSource(str, Enum):
    """Data source enumeration for tracking where data comes from."""
    SWIGGY = "SWIGGY"
    BIGBASKET = "BIGBASKET"
    ZOMATO = "ZOMATO"
    AMAZON_FRESH = "AMAZON_FRESH"
    GROFERS = "GROFERS"
    UNKNOWN = "UNKNOWN"


class VegStatus(str, Enum):
    """Vegetarian status enumeration."""
    VEG = "VEG"
    NON_VEG = "NON_VEG"
    VEGAN = "VEGAN"
    UNKNOWN = "UNKNOWN"


class ProcessingLevel(str, Enum):
    """Food processing level enumeration."""
    UNPROCESSED_MINIMAL_PROCESSED = "UNPROCESSED_MINIMAL_PROCESSED"
    PROCESSED_CULINARY_INGREDIENTS = "PROCESSED_CULINARY_INGREDIENTS"
    PROCESSED_FOOD = "PROCESSED_FOOD"
    ULTRA_PROCESSED = "ULTRA_PROCESSED"


# Base models for DRY
class TimestampMixin(SQLModel):
    """Mixin for timestamp fields - only for core entities that track changes."""
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class BaseResponse(SQLModel):
    """Base response model with common fields."""
    id: int


# User models
class User(TimestampMixin, table=True):
    """User table model."""
    __table_args__ = (UniqueConstraint("username"), UniqueConstraint("email"))
    
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    email: str = Field(index=True)
    full_name: Optional[str] = None
    hashed_password: str
    is_active: bool = Field(default=True)


class UserCreate(SQLModel):
    """User creation model."""
    username: str
    email: str
    full_name: Optional[str] = None
    password: str


class UserResponse(BaseResponse):
    """User response model."""
    username: str
    email: str
    full_name: Optional[str] = None
    is_active: bool


# Category models
class SuperCategory(TimestampMixin, table=True):
    """Super category table model."""
    __table_args__ = (UniqueConstraint("name"),)
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    image_filename: Optional[str] = None
    taxonomy_type: Optional[str] = None
    
    # Relationships
    categories: List["Category"] = Relationship(back_populates="super_category")
    products: List["Product"] = Relationship(back_populates="super_category")


class Category(TimestampMixin, table=True):
    """Category table model."""
    __table_args__ = (UniqueConstraint("name", "super_category_id"),)
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    image_filename: Optional[str] = None
    super_category_id: int = Field(foreign_key="supercategory.id", index=True)
    product_count: int = Field(default=0)
    age_consent_required: bool = Field(default=False)
    
    # Relationships
    super_category: SuperCategory = Relationship(back_populates="categories")
    products: List["Product"] = Relationship(back_populates="category")


class SuperCategoryResponse(BaseResponse):
    """Super category response model."""
    name: str
    image_filename: Optional[str] = None
    taxonomy_type: Optional[str] = None
    product_count: Optional[int] = None


class CategoryResponse(BaseResponse):
    """Category response model."""
    name: str
    image_filename: Optional[str] = None
    product_count: int
    age_consent_required: bool


class SuperCategoryDetail(SuperCategoryResponse):
    """Detailed super category with categories."""
    categories: List[CategoryResponse] = []


# Brand models
class Brand(TimestampMixin, table=True):
    """Brand table model."""
    __table_args__ = (UniqueConstraint("name"),)
    
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    
    # Relationships
    products: List["Product"] = Relationship(back_populates="brand")


class BrandResponse(BaseResponse):
    """Brand response model."""
    name: str
    product_count: Optional[int] = None


# Product model - matches actual data structure
class Product(TimestampMixin, table=True):
    """Product table model - contains all product information from data.json and parsed_ai.json."""
    __table_args__ = (
        UniqueConstraint("primary_source", "primary_external_id", "primary_external_variation_id"),
        UniqueConstraint("barcode"),
    )
    
    id: Optional[int] = Field(default=None, primary_key=True)
    
    # Basic product info from data.json
    name: str = Field(index=True)  # product_name_without_brand
    display_name: str = Field(index=True)  # variation.display_name
    
    # Primary data source
    primary_source: DataSource = Field(index=True)
    primary_external_id: str = Field(index=True)  # variation.id
    primary_external_variation_id: Optional[str] = Field(index=True)  # parent_product.product_id
    
    # References
    brand_id: int = Field(foreign_key="brand.id", index=True)
    super_category_id: int = Field(foreign_key="supercategory.id", index=True)
    category_id: int = Field(foreign_key="category.id", index=True)
    
    # Category hierarchy from data.json
    sub_category_l3: Optional[str] = Field(index=True)
    sub_category_l4: Optional[str] = Field(index=True)
    sub_category_l5: Optional[str] = Field(index=True)
    
    # Pricing from data.json -> variation.price
    mrp: Optional[float] = None
    store_price: Optional[float] = None
    offer_price: Optional[float] = None
    discount_value: Optional[float] = None
    unit_level_price: Optional[str] = None
    
    # Measurements from data.json -> variation
    quantity: Optional[str] = None
    unit_of_measure: Optional[str] = None
    weight_in_grams: Optional[float] = None
    volumetric_weight: Optional[float] = None
    sku_quantity_with_combo: Optional[str] = None
    
    # Product metadata from data.json -> variation
    product_type: Optional[str] = None  # scm_item_type
    filters_tag: Optional[str] = None
    
    # Health info from parsed_ai.json
    barcode: Optional[str] = Field(index=True)
    veg_status: Optional[VegStatus] = Field(index=True)  # veg_non_veg
    health_rating: Optional[int] = Field(index=True, ge=0, le=100)
    processing_level: Optional[ProcessingLevel] = Field(index=True)
    country_of_origin: Optional[str] = None
    
    # Nutrition info from parsed_ai.json
    net_quantity_value: Optional[float] = None
    net_quantity_unit: Optional[str] = None
    nutrition_serving_value: Optional[float] = None
    nutrition_serving_unit: Optional[str] = None
    approx_serves_per_pack: Optional[int] = None
    ingredients_string: Optional[str] = None
    
    # Instructions from parsed_ai.json
    storage_instructions: Optional[str] = None
    cooking_instructions: Optional[str] = None
    
    # JSON fields for arrays from parsed_ai.json (simple approach)
    allergens: Optional[str] = None  # JSON array
    certifications: Optional[str] = None  # JSON array
    positive_health_aspects: Optional[str] = None  # JSON array
    negative_health_aspects: Optional[str] = None  # JSON array
    preservatives: Optional[str] = None  # JSON array
    ins_numbers_found: Optional[str] = None  # JSON array
    additives: Optional[str] = None  # JSON array
    alarming_ingredients: Optional[str] = None  # JSON array
    
    # Relationships
    brand: Brand = Relationship(back_populates="products")
    super_category: SuperCategory = Relationship(back_populates="products")
    category: Category = Relationship(back_populates="products")
    nutrition_facts: List["NutritionFact"] = Relationship(back_populates="product")
    ingredients: List["Ingredient"] = Relationship(back_populates="product")
    source_mappings: List["ProductSourceMapping"] = Relationship(back_populates="product")
    images: List["ProductImage"] = Relationship(back_populates="product")


# Simple product details - embedded in main product table to match data structure
class ProductImage(SQLModel, table=True):
    """Product images - simple table without timestamps."""
    __table_args__ = (UniqueConstraint("product_id", "filename"),)
    
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    filename: str
    order_index: int = Field(default=0)
    is_primary: bool = Field(default=False)
    
    # Relationship
    product: "Product" = Relationship(back_populates="images")


# Source mapping table
class ProductSourceMapping(TimestampMixin, table=True):
    """Track external source mappings for products across platforms."""
    __table_args__ = (UniqueConstraint("source", "external_id", "external_variation_id"),)
    
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    source: DataSource = Field(index=True)
    external_id: str = Field(index=True)
    external_variation_id: Optional[str] = Field(index=True)
    external_brand_id: Optional[str] = None
    external_category_id: Optional[str] = None
    last_synced: datetime = Field(default_factory=datetime.utcnow)
    is_active: bool = Field(default=True)
    
    # Relationship
    product: Product = Relationship(back_populates="source_mappings")


# Nutrition models - simple, no timestamps needed
class NutritionFact(SQLModel, table=True):
    """Nutrition fact table model - from parsed_ai.json -> nutrition_info_table."""
    __table_args__ = (UniqueConstraint("product_id", "nutrient"),)
    
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    nutrient: str = Field(index=True)
    value: float
    unit: str
    rda_percentage: Optional[float] = None
    
    # Relationships
    product: Product = Relationship(back_populates="nutrition_facts")


class NutritionFactResponse(SQLModel):
    """Nutrition fact response model."""
    id: int
    nutrient: str
    value: float
    unit: str
    rda_percentage: Optional[float] = None


# Ingredient models - simple, no timestamps needed  
class Ingredient(SQLModel, table=True):
    """Ingredient table model - from parsed_ai.json -> parsed_ingredients."""
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    name: str = Field(index=True)
    percentage: Optional[float] = None
    is_alarming: bool = Field(default=False, index=True)
    alarming_reason: Optional[str] = None
    order_index: int = Field(default=0)
    
    # JSON fields for arrays (simpler than separate tables)
    ins_numbers: Optional[str] = None  # JSON array
    additives: Optional[str] = None  # JSON array
    
    # Relationships
    product: Product = Relationship(back_populates="ingredients")


class IngredientResponse(SQLModel):
    """Ingredient response model."""
    id: int
    name: str
    percentage: Optional[float] = None
    ins_numbers: List[str] = []
    additives: List[str] = []
    is_alarming: bool
    alarming_reason: Optional[str] = None


# Response models - using inheritance to avoid duplication
class ProductListItem(SQLModel):
    """Product list item for search results."""
    id: int
    name: str
    display_name: str
    brand: BrandResponse
    veg_status: Optional[VegStatus] = None
    health_rating: Optional[int] = None
    processing_level: Optional[ProcessingLevel] = None
    
    # Pricing (from ProductPricing)
    mrp: Optional[float] = None
    store_price: Optional[float] = None
    offer_price: Optional[float] = None
    discount_value: Optional[float] = None
    
    # Measurements (from ProductMeasurement)
    quantity: Optional[str] = None
    weight_in_grams: Optional[float] = None
    unit_of_measure: Optional[str] = None
    
    # Categories
    sub_category_l3: Optional[str] = None
    sub_category_l4: Optional[str] = None
    sub_category_l5: Optional[str] = None
    
    # Images
    primary_image: Optional[str] = None


class ProductDetail(ProductListItem):
    """Complete product details - extends ProductListItem."""
    primary_source: DataSource
    primary_external_id: str
    primary_external_variation_id: Optional[str] = None
    super_category: SuperCategoryResponse
    category: CategoryResponse
    
    # Extended pricing
    unit_level_price: Optional[str] = None
    
    # Extended measurements
    volumetric_weight: Optional[float] = None
    sku_quantity_with_combo: Optional[str] = None
    
    # All images
    images: List[str] = []
    
    # Additional info
    barcode: Optional[str] = None
    country_of_origin: Optional[str] = None
    
    # Nutrition
    net_quantity_value: Optional[float] = None
    net_quantity_unit: Optional[str] = None
    nutrition_serving_value: Optional[float] = None
    nutrition_serving_unit: Optional[str] = None
    approx_serves_per_pack: Optional[int] = None
    ingredients_string: Optional[str] = None
    
    # Health & safety
    storage_instructions: Optional[str] = None
    cooking_instructions: Optional[str] = None
    
    # Related data
    ingredients: List[IngredientResponse] = []
    nutrition_facts: List[NutritionFactResponse] = []
    allergens: List[str] = []
    certifications: List[str] = []
    positive_health_aspects: List[str] = []
    negative_health_aspects: List[str] = []
    tags: List[str] = []
    
    # Timestamps
    created_at: datetime
    updated_at: datetime


# Authentication models
class Token(SQLModel):
    """Token model."""
    access_token: str
    token_type: str = "bearer"


class TokenData(SQLModel):
    """Token data model."""
    username: Optional[str] = None


# Search and filter models
class ProductSearchFilter(SQLModel):
    """Product search and filter parameters."""
    query: Optional[str] = None
    brand_name: Optional[str] = None
    barcode: Optional[str] = None
    super_category_id: Optional[int] = None
    category_id: Optional[int] = None
    sub_category_l3: Optional[str] = None
    sub_category_l4: Optional[str] = None
    sub_category_l5: Optional[str] = None
    veg_status: Optional[VegStatus] = None
    min_health_rating: Optional[int] = Field(None, ge=0, le=100)
    max_health_rating: Optional[int] = Field(None, ge=0, le=100)
    processing_level: Optional[ProcessingLevel] = None
    min_price: Optional[float] = None
    max_price: Optional[float] = None
    sort_by: Optional[str] = Field("name", regex="^(name|price|health_rating|created_at)$")
    sort_order: Optional[str] = Field("asc", regex="^(asc|desc)$")
    limit: int = Field(20, le=100)
    offset: int = Field(0, ge=0)


class ProductSearchResponse(SQLModel):
    """Product search response model."""
    products: List[ProductListItem]
    total: int
    limit: int
    offset: int
    filters_applied: Optional[ProductSearchFilter] = None


class ImageInfo(SQLModel):
    """Image information model."""
    url: str
    filename: str
    path: str
    is_primary: bool = False


class ProductImagesResponse(SQLModel):
    """Product images response model."""
    product_id: int
    images: List[ImageInfo]