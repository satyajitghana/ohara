#!/usr/bin/env python3
"""
Test script to verify the refactored Swiggy scraper setup.
"""

import sys
from pathlib import Path

# Add the current directory to Python path for imports
sys.path.append(str(Path(__file__).parent))

def test_imports():
    """Test that all imports work correctly."""
    print("🧪 Testing imports...")
    
    try:
        from utils.common import load_config, save_json, print_category_summary, print_directory_structure_summary
        from utils.api import fetch_swiggy_home_api, extract_categories_from_response
        from utils.scraper import setup_api_interceptors, navigate_with_retry
        print("✅ All imports successful")
        return True
    except Exception as e:
        print(f"❌ Import error: {e}")
        return False

def test_config():
    """Test configuration loading."""
    print("🧪 Testing configuration...")
    
    try:
        from utils.common import load_config
        config = load_config()
        
        # Check required config sections
        required_sections = ['api', 'stores', 'scraping', 'timeouts', 'output', 'headers', 'cookies']
        for section in required_sections:
            if section not in config:
                raise ValueError(f"Missing config section: {section}")
        
        print(f"✅ Config loaded successfully")
        print(f"   Base URL: {config['api']['base_url']}")
        print(f"   Default Store ID: {config['stores']['default']['store_id']}")
        print(f"   Output Directory: {config['output']['base_directory']}")
        print(f"   Categories Subdirectory: {config['output']['categories_subdirectory']}")
        print(f"   Max Concurrent Categories: {config['scraping']['max_concurrent_categories']}")
        return True
    except Exception as e:
        print(f"❌ Config error: {e}")
        return False

def test_directory_structure():
    """Test directory structure functions."""
    print("🧪 Testing directory structure functions...")
    
    try:
        from utils.common import ensure_directory, create_safe_filename
        
        # Test safe filename creation
        test_names = ["Test Category", "Special/Chars\\Test", "   Spaces   "]
        for name in test_names:
            safe_name = create_safe_filename(name)
            print(f"   '{name}' -> '{safe_name}'")
        
        print("✅ Directory structure functions working")
        return True
    except Exception as e:
        print(f"❌ Directory structure error: {e}")
        return False

def main():
    """Run all tests."""
    print("🚀 Testing Swiggy Scraper v3 Setup\n")
    
    tests = [
        ("Import Test", test_imports),
        ("Configuration Test", test_config),
        ("Directory Structure Test", test_directory_structure)
    ]
    
    results = []
    for test_name, test_func in tests:
        print(f"\n{test_name}:")
        result = test_func()
        results.append((test_name, result))
    
    print(f"\n{'='*60}")
    print("📊 TEST RESULTS SUMMARY")
    print(f"{'='*60}")
    
    passed = 0
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} {test_name}")
        if result:
            passed += 1
    
    print(f"\nOverall: {passed}/{len(tests)} tests passed")
    
    if passed == len(tests):
        print("🎉 All tests passed! The scraper is ready to use.")
        print("\n📋 Next Steps:")
        print("   1. Run: python step1_scrape_home_v2.py")
        print("   2. Run: python step2_scrape_categories.py")
        return 0
    else:
        print("❌ Some tests failed. Please check the errors above.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
