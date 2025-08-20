from google import genai
import json
from pathlib import Path
from utils.config import get_api_config, get_directories_config, get_processing_config, suppress_grpc_logging
from utils.file_operations import (
    find_all_variation_paths, has_ai_output, get_image_paths, 
    create_ai_output_path, save_json
)
from utils.ai_client import setup_gemini_client, send_to_gemini
from utils.prompt_builder import build_prompt_parts
from utils.schemas import AiResponse
from utils.console_utils import (
    get_console, print_success, print_warning, print_error, 
    print_info, create_header
)


# --- Configuration and Setup ---

def load_api_key():
    """Load API key from config."""
    api_config = get_api_config()
    api_key = api_config.get("gemini_api_key")
    if not api_key:
        raise ValueError("API key not found in config.json")
    return api_key

# --- Main Processing Logic ---

def process_single_variation(client, variation_path: Path, enable_ocr: bool = True):
    """Process a single variation with AI analysis."""
    try:
        print_info(f"Processing variation: {variation_path.parent.name}/{variation_path.name}")
        
        # Check if already processed
        if has_ai_output(variation_path):
            print_warning(f"Already processed: {variation_path.name}")
            return True
        
        # Get image paths
        image_paths = get_image_paths(variation_path)
        if not image_paths:
            print_warning(f"No images found for variation {variation_path.name}")
            return False
        
        print_info(f"Found {len(image_paths)} images to process")
        
        # Build prompt
        prompt_parts, _ = build_prompt_parts(variation_path, enable_ocr)
        
        # Send to Gemini
        response = send_to_gemini(client, prompt_parts, AiResponse)
        
        # Process response
        if response.parsed:
            ai_output_dict = response.parsed.model_dump()
            output_path = create_ai_output_path(variation_path)
            save_json(ai_output_dict, output_path)
            print_success(f"Successfully processed {variation_path.name}")
            return True
        else:
            # Fallback to parsing text
            try:
                cleaned_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
                ai_output_dict = json.loads(cleaned_text)
                output_path = create_ai_output_path(variation_path)
                save_json(ai_output_dict, output_path)
                print_success(f"Successfully processed {variation_path.name} (fallback)")
                return True
            except json.JSONDecodeError:
                print_error(f"Failed to decode JSON from model response for {variation_path.name}")
                print(f"Raw response: {response.text}")
                return False
    
    except Exception as e:
        print_error(f"Failed to process {variation_path.name}: {e}")
        return False


def main():
    """Main function to run the AI processing."""
    # Suppress verbose gRPC logging
    suppress_grpc_logging()
    
    console = get_console()
    
    try:
        # Print header
        header = create_header(
            "🤖 AI Image Processor (Single)", 
            "Processing product images with AI analysis"
        )
        console.print(header)
        
        # Load configuration
        api_key = load_api_key()
        directories = get_directories_config()
        processing_config = get_processing_config()
        
        # Validate OCR requirements if enabled
        enable_ocr = processing_config.get('enable_ocr', True)
        if enable_ocr:
            from utils.ocr_utils import validate_ocr_requirements
            validate_ocr_requirements()
            print_info("OCR enabled and validated")
        else:
            print_info("OCR disabled")
        
        # Setup client
        client = setup_gemini_client(api_key)
        
        # Get base path
        base_path = Path(directories['scraped_data'])
        if not base_path.exists():
            print_error(f"Scraped data directory not found: {base_path}")
            return
        
        # For single processing, let's process the first brand with variations
        brand_dirs = [d for d in base_path.iterdir() if d.is_dir()]
        if not brand_dirs:
            print_error("No brand directories found")
            return
        
        # Take first brand for demo
        brand_dir = brand_dirs[0]
        print_info(f"Processing brand: {brand_dir.name}")
        
        # Find variations in this brand
        variation_paths = []
        for item in brand_dir.iterdir():
            if (item.is_dir() and 
                item.name not in ["brand_info.json", "products_list.json"] and
                (item / "images").exists() and 
                any((item / "images").iterdir())):
                variation_paths.append(item)
        
        if not variation_paths:
            print_error(f"No variations with images found in {brand_dir}")
            return
        
        print_info(f"Found {len(variation_paths)} variations to process")
        
        # Process each variation
        success_count = 0
        for variation_path in variation_paths:
            if process_single_variation(client, variation_path, enable_ocr):
                success_count += 1
        
        print_success(f"Processed {success_count}/{len(variation_paths)} variations successfully")
        
    except (FileNotFoundError, ValueError) as e:
        print_error(f"Configuration error: {e}")
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
