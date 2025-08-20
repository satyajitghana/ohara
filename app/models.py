"""Database models using SQLModel."""
from typing import Optional, List
from datetime import datetime
from sqlmodel import SQLModel, Field, Relationship
from enum import Enum


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


# User models
class UserBase(SQLModel):
    """Base user model."""
    username: str = Field(index=True, unique=True)
    email: str = Field(index=True, unique=True)
    full_name: Optional[str] = None
    is_active: bool = Field(default=True)


class User(UserBase, table=True):
    """User table model."""
    id: Optional[int] = Field(default=None, primary_key=True)
    hashed_password: str
    created_at: datetime = Field(default_factory=datetime.utcnow)


class UserCreate(UserBase):
    """User creation model."""
    password: str


class UserPublic(UserBase):
    """User public model."""
    id: int
    created_at: datetime


# Brand models
class BrandBase(SQLModel):
    """Base brand model."""
    name: str = Field(index=True)
    original_brand_id: str = Field(index=True, unique=True)


class Brand(BrandBase, table=True):
    """Brand table model."""
    id: Optional[int] = Field(default=None, primary_key=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    products: List["Product"] = Relationship(back_populates="brand")


class BrandPublic(BrandBase):
    """Brand public model."""
    id: int
    product_count: Optional[int] = None


# Product models
class ProductBase(SQLModel):
    """Base product model."""
    name: str = Field(index=True)
    display_name: str = Field(index=True)
    original_product_id: str = Field(index=True, unique=True)
    
    # Pricing
    mrp: Optional[float] = None
    store_price: Optional[float] = None
    offer_price: Optional[float] = None
    discount_value: Optional[float] = None
    
    # Product details
    quantity: Optional[str] = None
    unit_of_measure: Optional[str] = None
    weight_in_grams: Optional[float] = None
    
    # Categories
    category: Optional[str] = Field(index=True)
    super_category: Optional[str] = Field(index=True)
    sub_category_l3: Optional[str] = Field(index=True)
    sub_category_l4: Optional[str] = Field(index=True)
    sub_category_l5: Optional[str] = Field(index=True)
    
    # Nutritional & AI Info
    barcode: Optional[str] = Field(index=True, unique=True)
    net_quantity_value: Optional[float] = None
    net_quantity_unit: Optional[str] = None
    veg_status: Optional[VegStatus] = Field(index=True)
    health_rating: Optional[int] = Field(index=True, ge=0, le=100)
    processing_level: Optional[ProcessingLevel] = Field(index=True)
    country_of_origin: Optional[str] = None
    
    # JSON fields for complex data
    ingredients_string: Optional[str] = None
    allergens: Optional[str] = None  # JSON string
    certifications: Optional[str] = None  # JSON string
    positive_health_aspects: Optional[str] = None  # JSON string
    negative_health_aspects: Optional[str] = None  # JSON string
    storage_instructions: Optional[str] = None
    cooking_instructions: Optional[str] = None
    
    # Nutrition info
    nutrition_serving_value: Optional[float] = None
    nutrition_serving_unit: Optional[str] = None
    approx_serves_per_pack: Optional[int] = None
    
    # Image paths
    image_paths: Optional[str] = None  # JSON string of image paths


class Product(ProductBase, table=True):
    """Product table model."""
    id: Optional[int] = Field(default=None, primary_key=True)
    brand_id: int = Field(foreign_key="brand.id", index=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
    
    # Relationships
    brand: Brand = Relationship(back_populates="products")
    nutrition_facts: List["NutritionFact"] = Relationship(back_populates="product")
    ingredients: List["Ingredient"] = Relationship(back_populates="product")


class ProductPublic(ProductBase):
    """Product public model."""
    id: int
    brand: BrandPublic
    created_at: datetime


class ProductDetail(ProductPublic):
    """Detailed product model with nutrition and ingredients."""
    nutrition_facts: List["NutritionFactPublic"] = []
    ingredients: List["IngredientPublic"] = []
    
    class Config:
        from_attributes = True


# Nutrition models
class NutritionFactBase(SQLModel):
    """Base nutrition fact model."""
    nutrient: str = Field(index=True)
    value: float
    unit: str
    rda_percentage: Optional[float] = None


class NutritionFact(NutritionFactBase, table=True):
    """Nutrition fact table model."""
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    
    # Relationships
    product: Product = Relationship(back_populates="nutrition_facts")


class NutritionFactPublic(NutritionFactBase):
    """Nutrition fact public model."""
    id: int


# Ingredient models
class IngredientBase(SQLModel):
    """Base ingredient model."""
    name: str = Field(index=True)
    percentage: Optional[float] = None
    ins_numbers: Optional[str] = None  # JSON string
    additives: Optional[str] = None  # JSON string
    is_alarming: bool = Field(default=False, index=True)
    alarming_reason: Optional[str] = None


class Ingredient(IngredientBase, table=True):
    """Ingredient table model."""
    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id", index=True)
    
    # Relationships
    product: Product = Relationship(back_populates="ingredients")


class IngredientPublic(IngredientBase):
    """Ingredient public model."""
    id: int


# Authentication models
class Token(SQLModel):
    """Token model."""
    access_token: str
    token_type: str = "bearer"


class TokenData(SQLModel):
    """Token data model."""
    username: Optional[str] = None


# Search and filter models
class ProductSearchParams(SQLModel):
    """Product search parameters."""
    query: Optional[str] = None
    brand_name: Optional[str] = None
    category: Optional[str] = None
    super_category: Optional[str] = None
    veg_status: Optional[VegStatus] = None
    min_health_rating: Optional[int] = Field(None, ge=0, le=100)
    max_health_rating: Optional[int] = Field(None, ge=0, le=100)
    processing_level: Optional[ProcessingLevel] = None
    sort_by: Optional[str] = Field("name", regex="^(name|price|health_rating|created_at)$")
    sort_order: Optional[str] = Field("asc", regex="^(asc|desc)$")
    limit: int = Field(20, le=100)
    offset: int = Field(0, ge=0)


class CategoryInfo(SQLModel):
    """Category information model."""
    name: str
    count: int
    super_categories: Optional[List[str]] = None


class ProductListResponse(SQLModel):
    """Product list response model."""
    products: List[ProductPublic]
    total: int
    limit: int
    offset: int
