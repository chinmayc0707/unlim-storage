import asyncio
from playwright.async_api import async_playwright
import subprocess
import time

async def main():
    process = subprocess.Popen(["python3", "app.py"])
    time.sleep(2)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Catch console messages to debug
            page.on("console", lambda msg: print(f"Browser console: {msg.text}"))

            await page.goto("http://localhost:5000/login")

            # Register
            await page.click("text=Create Account")
            await page.fill("#reg-phone-input", "+12345")
            await page.fill("#reg-password-input", "pass")
            await page.click("text=Register")
            await page.wait_for_timeout(1000)

            # Login
            await page.fill("#phone-input", "+12345")
            await page.fill("#password-input", "pass")
            await page.click("button.primary-btn:has-text('Login')")
            await page.wait_for_timeout(2000)

            print("Current URL:", page.url)

            if "login" in page.url:
                print("Failed to login")
            else:
                # Should be on index
                await page.wait_for_selector(".new-btn")
                await page.click(".new-btn")
                await page.wait_for_timeout(500)
                await page.click("text=New folder")
                await page.wait_for_selector("#folder-name-input")
                await page.fill("#folder-name-input", "TestFolder")
                await page.click("text=Create")
                await page.wait_for_timeout(1000)

                content = await page.content()
                if "TestFolder" in content:
                    print("Frontend E2E: Folder creation successful")
                else:
                    print("Frontend E2E: Folder creation failed")

            await browser.close()

    finally:
        process.terminate()

asyncio.run(main())
