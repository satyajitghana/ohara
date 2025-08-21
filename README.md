
# Ohara Product API

A FastAPI backend with JWT authentication for product information with nutritional data and AI analysis.

## Prerequisites

```bash
sudo apt install tesseract-ocr
```

## Installation

```bash
# Install dependencies
pip install -e .
```

## Database Migration

Run the migration script to import scraped data into the database:

```bash
python -m app.scripts.migrate_data
```

## Running the API

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

The API will be available at `http://localhost:8000`

- API Documentation: `http://localhost:8000/docs`
- Alternative docs: `http://localhost:8000/redoc`

## Create a User

```bash
python -m app.scripts.make_user <username> <password> [email] [full_name]
```

Example:
```bash
python -m app.scripts.make_user admin mypassword admin@example.com "Admin User"
```

## API Endpoints

### Authentication
- `POST /auth/register` - Register a new user
- `POST /auth/token` - Login and get access token
- `GET /auth/me` - Get current user info

### Products
- `GET /products/search` - Search products with filters
- `GET /products/{product_id}` - Get detailed product info
- `GET /products/barcode/{barcode}` - Get product by barcode

### Categories
- `GET /categories/` - Get all categories
- `GET /categories/super` - Get super categories
- `GET /categories/{category_name}/products` - Get products by category

### Brands
- `GET /brands/` - Get all brands
- `GET /brands/{brand_id}/products` - Get products by brand

### Images
- `GET /images/{image_path}` - Serve product images (use paths from image info API)
- `GET /images/product/{product_id}/images` - Get detailed image information for a product

### Nutrition & Advanced Queries
- `GET /nutrition/allergen-free` - Get allergen-free products
- `GET /nutrition/high-protein` - Get high-protein products
- `GET /nutrition/low-fat` - Get low-fat products
- `GET /nutrition/nutrient/{nutrient_name}` - Get products by specific nutrient
- `GET /nutrition/ingredients/avoid` - Get products without specified ingredients

All product endpoints require authentication.