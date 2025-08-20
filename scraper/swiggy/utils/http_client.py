"""HTTP client utilities."""
import asyncio
import httpx
from typing import Dict, Any, Optional
from rich.console import Console

from .config import get_api_config


async def create_http_client(timeout: Optional[float] = None) -> httpx.AsyncClient:
    """Create an HTTP client with default configuration."""
    api_config = get_api_config()
    client_timeout = timeout or api_config.get('timeout', 30.0)
    
    return httpx.AsyncClient(timeout=client_timeout)


def get_default_headers() -> Dict[str, str]:
    """Get default headers for API requests."""
    api_config = get_api_config()
    return api_config.get('headers', {})


async def make_api_request(client: httpx.AsyncClient, url: str, 
                          params: Dict[str, Any], 
                          headers: Optional[Dict[str, str]] = None) -> httpx.Response:
    """Make an API request with error handling."""
    if headers is None:
        headers = get_default_headers()
    
    response = await client.get(url, headers=headers, params=params)
    response.raise_for_status()
    return response


async def download_image(client: httpx.AsyncClient, image_id: str, 
                        download_path: str, semaphore: asyncio.Semaphore) -> bool:
    """Download an image from Swiggy's CDN."""
    async with semaphore:
        api_config = get_api_config()
        base_url = api_config.get('image_base_url', '')
        image_url = f"{base_url}{image_id}"
        
        try:
            timeout = api_config.get('download_timeout', 20.0)
            response = await client.get(image_url, timeout=timeout)
            response.raise_for_status()
            
            with open(download_path, 'wb') as f:
                f.write(response.content)
            return True
        except httpx.HTTPStatusError as e:
            Console().print(
                f"  [bold red]❌ HTTP ERROR[/bold red] downloading {image_url}: "
                f"{e.response.status_code}"
            )
            return False
        except Exception as e:
            Console().print(
                f"  [bold red]❌ Unexpected error[/bold red] downloading {image_url}: "
                f"{type(e).__name__} - {e}"
            )
            return False
