"""Image serving routes."""
import os
import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Response, Depends
from fastapi.responses import FileResponse

from ..database import SessionDep
from ..models import Product, ProductImagesResponse, ImageInfo
from ..auth import get_current_active_user

router = APIRouter(prefix="/images", tags=["images"])


@router.get("/{image_path:path}")
def serve_image(image_path: str):
    """Serve product images from scraped_data directory."""
    # Construct the full path
    full_path = Path("scraped_data") / image_path
    
    # Security check: ensure the path is within scraped_data directory
    try:
        resolved_path = full_path.resolve()
        scraped_data_path = Path("scraped_data").resolve()
        
        # Check if the resolved path is within scraped_data directory
        if not str(resolved_path).startswith(str(scraped_data_path)):
            raise HTTPException(status_code=403, detail="Access forbidden")
        
        # Check if file exists
        if not resolved_path.exists() or not resolved_path.is_file():
            raise HTTPException(status_code=404, detail="Image not found")
        
        # Determine content type based on file extension
        file_extension = resolved_path.suffix.lower()
        content_type_map = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
            '.bmp': 'image/bmp',
            '.svg': 'image/svg+xml'
        }
        
        content_type = content_type_map.get(file_extension, 'application/octet-stream')
        
        return FileResponse(
            path=resolved_path,
            media_type=content_type,
            filename=resolved_path.name
        )
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error serving image: {str(e)}")


@router.get("/product/{product_id}/images", response_model=ProductImagesResponse)
def get_product_images(
    product_id: int,
    session: SessionDep,
    _: Optional[str] = Depends(get_current_active_user)
) -> ProductImagesResponse:
    """Get detailed image information for a product."""
    # Get product
    product = session.get(Product, product_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    
    images = []
    
    # Parse image paths and catalog images
    image_paths = []
    catalog_images = []
    
    if product.image_paths:
        try:
            image_paths = json.loads(product.image_paths)
        except json.JSONDecodeError:
            pass
    
    if product.catalog_images:
        try:
            catalog_images = json.loads(product.catalog_images)
        except json.JSONDecodeError:
            pass
    
    # Create image info objects
    for i, image_path in enumerate(image_paths):
        filename = Path(image_path).name
        catalog_name = catalog_images[i] if i < len(catalog_images) else None
        
        images.append(ImageInfo(
            url=f"/images/{image_path}",
            filename=filename,
            catalog_name=catalog_name
        ))
    
    return ProductImagesResponse(
        product_id=product_id,
        images=images
    )
