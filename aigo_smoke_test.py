import asyncio
import os
from playwright.async_api import async_playwright
from Core.Intelligence.aigo_suite import AIGOSuite

async def test_aigo_healing():
    print("\n--- Starting AIGO Smoke Test ---")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context()
        page = await context.new_page()
        await page.goto("https://www.google.com") # Just a dummy page
        
        @AIGOSuite.aigo_retry(
            max_retries=1, 
            delay=1.0, 
            context_key="google_test", 
            element_key="non_existent_button", 
            use_aigo=True
        )
        async def failing_action(page):
            print("    [Test] Attempting action with non-existent selector...")
            # This will fail
            await page.click("#non-existent-id-12345", timeout=2000)

        try:
            await failing_action(page=page)
        except Exception as e:
            print(f"\n--- [RESULT] Test finished. Expected failure caught: {e} ---")
            print("Check logs above for '[AIGO HEAL]' and 'Triggering AI healing' messages.")
        
        await browser.close()

if __name__ == "__main__":
    asyncio.run(test_aigo_healing())
