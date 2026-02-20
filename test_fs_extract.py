import asyncio
from playwright.async_api import async_playwright
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from Modules.Flashscore.fs_schedule import extract_matches_from_page

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64)")
        page = await context.new_page()
        print("Navigating...")
        await page.goto("https://www.flashscore.com/football/", wait_until="domcontentloaded")
        await asyncio.sleep(5)
        
        # Click Scheduled tab (equivalent to manager.py)
        try:
            tab = page.locator('.filters__tab[data-analytics-alias="scheduled"]')
            if await tab.count() > 0:
                print("Clicking Scheduled Tab...")
                await tab.first.click()
                await asyncio.sleep(3)
        except Exception as e:
            print("Tab error:", e)
        
        print("Extracting...")
        matches = await extract_matches_from_page(page)
        print(f"Found {len(matches)} matches")
        if matches:
            print("First match:", matches[0])
            
        await browser.close()

asyncio.run(main())
