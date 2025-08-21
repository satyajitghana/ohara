from google import genai
import json
from pathlib import Path
import os
import multiprocessing
from functools import partial
import logging
from utils.config import get_api_config, get_directories_config, get_processing_config, suppress_grpc_logging
from utils.file_operations import find_all_variation_paths, has_ai_output, save_json
from utils.ai_client import setup_gemini_client, send_to_gemini
from utils.prompt_builder import build_prompt_parts
from utils.schemas import AiResponse
from utils.console_utils import (
    get_console, get_progress_bar, print_success, print_error,
    print_info, create_header, create_summary_table, print_banner
)
import os
os.environ["GRPC_VERBOSITY"] = "ERROR"      # Only show errors from gRPC
os.environ["GLOG_minloglevel"] = "2"        # Limit Abseil (GLOG) logs to errors

# --- Configuration and Logging Setup ---

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def load_api_key():
    """Load API key from config."""
    api_config = get_api_config()
    api_key = api_config.get("gemini_api_key")
    if not api_key:
        raise ValueError("API key not found in config.json")
    return api_key

# --- Core Processing Functions ---

def process_variation(variation_path: Path, enable_ocr: bool = True):
    """Worker function to process a single product variation."""
    try:
        # Check if already processed
        if has_ai_output(variation_path):
            return f"Skipped: {variation_path.parent.name}/{variation_path.name}"

        # Setup client (API key is set as environment variable)
        client = genai.Client()

        # Build prompt and get image paths
        prompt_parts, image_paths = build_prompt_parts(variation_path, enable_ocr=enable_ocr)

        if not image_paths:
            return f"No images: {variation_path.parent.name}/{variation_path.name}"

        # Send to Gemini
        response = send_to_gemini(client, prompt_parts, AiResponse)
        
        if response.parsed:
            ai_output_dict = response.parsed.model_dump()
            output_path = variation_path / "parsed_ai.json"
            save_json(ai_output_dict, output_path)
            return f"Success: {variation_path.parent.name}/{variation_path.name}"
        else:
            # Fallback to parsing text
            try:
                cleaned_text = response.text.strip().removeprefix("```json").removesuffix("```").strip()
                ai_output_dict = json.loads(cleaned_text)
                output_path = variation_path / "parsed_ai.json"
                save_json(ai_output_dict, output_path)
                return f"Success (fallback): {variation_path.parent.name}/{variation_path.name}"
            except json.JSONDecodeError:
                 return f"JSON Error: {variation_path.parent.name}/{variation_path.name}"

    except Exception as e:
        logging.error(f"Failed to process {variation_path}: {e}")
        return f"Error: {variation_path.parent.name}/{variation_path.name} - {e}"

# --- Main Execution ---

def main():
    """Main function to find and process all products in parallel."""
    # Suppress verbose gRPC logging
    suppress_grpc_logging()
    
    console = get_console()
    
    try:
        # Print header
        header = create_header(
            "🚀 AI Image Processor (Parallel)", 
            "Processing all product images with AI analysis"
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
        
        # Set API key for worker processes
        os.environ["GEMINI_API_KEY"] = api_key
        
        # Get all variation paths from the new swiggy listings directory
        base_path = Path(directories['scraped_data']) / "swiggy" / "listings"
        all_variation_paths = find_all_variation_paths(base_path)
        
        if not all_variation_paths:
            print_error("No product variations with images found to process")
            return

        print_info(f"Found {len(all_variation_paths)} product variations to process")
        
        # Filter out already processed if skip_existing is True
        if processing_config.get('skip_existing', True):
            unprocessed_paths = [p for p in all_variation_paths if not has_ai_output(p)]
            print_info(f"Skipping {len(all_variation_paths) - len(unprocessed_paths)} already processed variations")
            all_variation_paths = unprocessed_paths
        
        if not all_variation_paths:
            print_info("All variations already processed")
            return

        print_banner("Starting Parallel Processing")
        
        # Get number of processes
        num_processes = processing_config.get('num_processes', 200)
        print_info(f"Using {num_processes} parallel processes")

        # Create partial function with enable_ocr parameter
        process_variation_with_config = partial(process_variation, enable_ocr=enable_ocr)

        # Progress tracking
        success_count = 0
        error_count = 0
        skip_count = 0
        
        with get_progress_bar() as progress:
            task = progress.add_task("[cyan]Processing Products...", total=len(all_variation_paths))

            with multiprocessing.Pool(processes=num_processes) as pool:
                for i, result in enumerate(pool.imap_unordered(process_variation_with_config, all_variation_paths)):
                    progress.update(task, advance=1, description=f"[cyan]Processing... {result}")
                    
                    # Count results
                    if "Success" in result:
                        success_count += 1
                    elif "Skipped" in result:
                        skip_count += 1
                    else:
                        error_count += 1

        # Final summary
        print_banner("Processing Complete")
        stats = {
            "Total Variations": len(all_variation_paths),
            "Successfully Processed": success_count,
            "Skipped": skip_count,
            "Errors": error_count,
            "Parallel Processes": num_processes
        }
        console.print(create_summary_table(stats))
        print_success("All product variations processed")
        
    except (FileNotFoundError, ValueError) as e:
        print_error(f"Configuration error: {e}")
    except Exception as e:
        print_error(f"An unexpected error occurred: {e}")

if __name__ == "__main__":
    main()
