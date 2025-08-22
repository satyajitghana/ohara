"""Image serving routes."""
import os
import json
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, HTTPException, Response, Depends
from fastapi.responses import FileResponse

from ..database import SessionDep
from ..models import Product, ProductImagesResponse, ImageInfo, ProductImage
from ..auth import get_current_active_user
from sqlmodel import select

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
    
    # Get product images from the ProductImage table
    image_statement = select(ProductImage).where(ProductImage.product_id == product_id).order_by(ProductImage.order_index)
    product_images = session.exec(image_statement).all()
    
    images = []
    for img in product_images:
        images.append(ImageInfo(
            url=f"/images/{img.filename}",
            filename=img.filename,
            path=img.filename,  # Using filename as path since we store the relative path
            is_primary=img.is_primary
        ))
    
    return ProductImagesResponse(
        product_id=product_id,
        images=images
    )
