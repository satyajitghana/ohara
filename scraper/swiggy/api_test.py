"""
Simple Swiggy API Test

Just comment/uncomment headers below to test what's needed.
"""

import httpx
import json
import asyncio
from datetime import datetime
from pathlib import Path
import random


async def test_swiggy_api():
    # API details
    url = "https://www.swiggy.com/api/instamart/category-listing"
    params = {
        'categoryName': 'Fresh Vegetables',
        'storeId': '1313712',
        'offset': '0',
        'filterName': '',
        'primaryStoreId': '1313712',
        'secondaryStoreId': '',
        'taxonomyType': 'Speciality taxonomy 1'
    }
    
    # Headers from your curl command - comment/uncomment to test
    headers = {
        # 'accept': '*/*',
        # 'accept-language': 'en-GB,en;q=0.9,en-US;q=0.8,hi;q=0.7',
        # 'cache-control': 'no-cache',
        # 'content-type': 'application/json',
        # 'cookie': '_device_id=fbdc0509-56de-ad55-b73e-27f6093d1f9f; __SW=jqjr2sWFbgPaKRHn45ozwj7tpgC7m8tf; _swuid=fbdc0509-56de-ad55-b73e-27f6093d1f9f; _cid=MTEzNzk0NDA%3D; fontsLoaded=1; _gcl_au=1.1.64566381.1755607930; _gid=GA1.2.1019067680.1755607930; deviceId=s%3Afbdc0509-56de-ad55-b73e-27f6093d1f9f.59m%2FBNnESZPfi8UWx0plBXN3PBV%2FKJn3aO32eu2daMo; versionCode=1200; platform=web; subplatform=dweb; statusBarHeight=0; bottomOffset=0; genieTrackOn=false; ally-on=false; isNative=false; strId=; openIMHP=false; lat=s%3A12.9753.8gmBoDSz860Bpgr4nz85WZn73wSUbE%2BrLIXLJ4kCars; lng=s%3A77.591.VwcRunP6ZcEhHD4LxxRu3NMQHGxGf42m82VdHR%2B4N48; address=s%3A.4Wx2Am9WLolnmzVcU32g6YaFDw0QbIBFRj2nkO7P25s; addressId=s%3A.4Wx2Am9WLolnmzVcU32g6YaFDw0QbIBFRj2nkO7P25s; LocSrc=s%3AswgyUL.Dzm1rLPIhJmB3Tl2Xs6141hVZS0ofGP7LGmLXgQOA7Y; webBottomBarHeight=0; _sid=mdybdf9d-b0e2-44eb-b760-80d04ca5886c; _ga=GA1.1.1900939893.1755607930; _is_logged_in=1; _session_tid=8d26b32ac31d9664456ff0fb865cd47d7f03b393bad498a520863873220d630ff2c83457eb37a5d6e877cab98ac5becabf1ca5e771f8e498591a891722aa7b81d8db44da036dbc3fbdbde365cb99c6371b87fd177c3855d2fa1b2cbef16a4350c77ca6824301ebe9e5c1141c4789e123; tid=s%3Ab73445a6-aae3-4f89-9ab3-880d4198b6dc.cJQJm1L8iN4bAq7TpWZM31SIWkqd3uT2rprVrjx79Ps; sid=s%3Amdybdf9d-b0e2-44eb-b760-80d04ca5886c.F2mUB7zHHWboT1QakBYSORBLOBP0FqUZ8qpk7e1HSsI; userLocation=%7B%22address%22%3A%22%22%2C%22lat%22%3A12.9753%2C%22lng%22%3A77.591%2C%22id%22%3A%22%22%2C%22annotation%22%3A%22%22%2C%22name%22%3A%22%22%7D; _ga_YE38MFJRBZ=GS2.1.s1755624127$o2$g1$t1755624443$j60$l0$h0; _ga_34JYJ0BCRN=GS2.1.s1755624127$o2$g1$t1755624443$j60$l0$h0; aws-waf-token=341f8d85-0670-41e5-838c-61b0d135644a:HgoAgUt5RhgZAAAA:A4dZxNFudzHZ/hXMnTx5DBdBNtt2tKUYbhlEL4SqLsj14thn4+7Rrg83NwxqEzNory71OiSk9swZF28QcY2bejy6lwCY2tr24Ik818bDWLVx702awqhELlm6C3BmLB6xSyPdMdddrN3knZhEQbcAgTW13B/HoYBT36xeJK5QN0ic1I9iVHyEPobMnC9K6nXfbPli3gIXzZg3Pa+UE36l6OJ5VAfRHMlVMHUMcfyGSW55D723Vyu2hDWzf2Q=; _ga_VEG1HFE5VZ=GS2.1.s1755624444$o2$g1$t1755624467$j37$l0$h0; _ga_8N8XRG907L=GS2.1.s1755624444$o2$g1$t1755624467$j37$l0$h0; _ga_0XZC5MS97H=GS2.1.s1755624444$o2$g1$t1755624467$j37$l0$h0',
        # 'dnt': '1',
        # 'matcher': '8ffc78eccd9bbdefba9d77d',
        # 'pragma': 'no-cache',
        # 'priority': 'u=1, i',
        # 'referer': 'https://www.swiggy.com/instamart/category-listing?categoryName=Fresh%20Vegetables&storeId=1313712&offset=0&filterName=&taxonomyType=Speciality%20taxonomy%201&showAgeConsent=false',
        # 'sec-fetch-dest': 'empty',
        # 'sec-fetch-mode': 'cors',
        # 'sec-fetch-site': 'same-origin',
        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
        'x-build-version': '2.291.0'
    }
    
    # Make the request
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            print(f"🔍 Testing API with {len(headers)} headers...")
            
            response = await client.get(url, headers=headers, params=params)
            
            print(f"Status Code: {response.status_code}")
            
            if response.status_code == 200:
                try:
                    data = response.json()
                    print("✅ SUCCESS! API returned JSON data")
                    print(f"Response keys: {list(data.keys()) if isinstance(data, dict) else 'Not a dict'}")
                    
                    # Save to JSON file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"swiggy_response_{timestamp}.json"
                    
                    # Create responses directory if it doesn't exist
                    responses_dir = Path("responses")
                    responses_dir.mkdir(exist_ok=True)
                    filepath = responses_dir / filename
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        json.dump(data, f, indent=2, ensure_ascii=False)
                    
                    print(f"💾 Response saved to: {filepath}")
                    
                    # Show some sample data
                    if isinstance(data, dict):
                        for key, value in list(data.items())[:3]:
                            print(f"  {key}: {str(value)[:100]}...")
                    
                    return data
                    
                except json.JSONDecodeError:
                    print("✅ SUCCESS but response is not JSON")
                    print(f"Response: {response.text[:200]}...")
                    
                    # Save text response to file
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                    filename = f"swiggy_response_{timestamp}.txt"
                    
                    # Create responses directory if it doesn't exist
                    responses_dir = Path("responses")
                    responses_dir.mkdir(exist_ok=True)
                    filepath = responses_dir / filename
                    
                    with open(filepath, 'w', encoding='utf-8') as f:
                        f.write(response.text)
                    
                    print(f"💾 Response saved to: {filepath}")
                    
                    return response.text
            else:
                print(f"❌ FAILED - Status: {response.status_code}")
                print(f"Response: {response.text[:200]}...")
                return None
                
        except Exception as e:
            print(f"❌ ERROR: {e}")
            return None

async def test_swiggy_images():
    # Image URL from user
    base_url = "https://media-assets.swiggy.com/swiggy/image/upload/"
    # image_id = "NI_CATALOG/IMAGES/CIW/2024/7/2/1f94576c-c0f6-4bde-b6fc-eeecce982881_79fe714e-a773-4488-967e-6bafce33c8e7"
    image_id = "5b0f010e1c9b2ebce6a965512a896ba6"

    # Different transformation parameters to test
    transformations = {
        "original_high_res": "", # No params, should be original
        "q_auto": "q_auto",
        "q_100": "q_100",
        "fl_lossy_q_auto": "fl_lossy,f_auto,q_auto",
        "fl_lossy_q_80": "fl_lossy,f_auto,q_80",
    }

    # Headers - simplified for image requests
    headers = {
        'user-agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_6 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.6 Mobile/15E148 Safari/604.1',
    }
    
    # Create responses directory if it doesn't exist
    images_dir = Path("responses/images")
    images_dir.mkdir(parents=True, exist_ok=True)

    async with httpx.AsyncClient(timeout=30.0) as client:
        for name, params in transformations.items():
            url = f"{base_url}{params}/{image_id}" if params else f"{base_url}{image_id}"
            print(f"🔍 Testing image URL: {url}")
            
            try:
                response = await client.get(url, headers=headers)
                
                print(f"Status Code: {response.status_code}")
                
                if response.status_code == 200:
                    # Deduce file extension
                    content_type = response.headers.get('content-type', 'image/jpeg')
                    extension = content_type.split('/')[-1]
                    
                    filename = f"image_{name}.{extension}"
                    filepath = images_dir / filename
                    
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    
                    print(f"💾 Image saved to: {filepath}")
                    
                else:
                    print(f"❌ FAILED to download {name} - Status: {response.status_code}")
                    print(f"Response: {response.text[:200]}...")

            except Exception as e:
                print(f"❌ ERROR downloading {name}: {e}")


async def main():
    print("🚀 Simple Swiggy API Test")
    print("Edit the headers dict above to test different combinations\n")
    await test_swiggy_api()

    print("\n🚀 Swiggy Image API Test")
    print("Testing different image transformation parameters...\n")
    await test_swiggy_images()


if __name__ == "__main__":
    asyncio.run(main())
