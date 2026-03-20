import asyncio
from playwright.async_api import async_playwright
import subprocess
import time

async def main():
    # Start app
    process = subprocess.Popen(["python3", "app.py"])
    time.sleep(2)

    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()

            # Go to home
            await page.goto("http://localhost:5000/")
            # Should redirect to /login due to 401 from /api/files in JS
            await page.wait_for_timeout(2000)

            # Since index is rendered, the JS will fail fetchFiles and redirect to /login
            print("Current URL:", page.url)

            # Register new user
            await page.goto("http://localhost:5000/login")
            await page.click("text=Create Account")
            await page.fill("#reg-phone-input", "+1999999")
            await page.fill("#reg-password-input", "mypassword")
            await page.click("text=Register")
            await page.wait_for_timeout(1000)

            # Should be on login now, fill and login
            await page.fill("#password-input", "mypassword")
            await page.click("text=Login")
            await page.wait_for_timeout(2000)

            # Should redirect to index and fetch files successfully
            print("Current URL after login:", page.url)

            # Create a folder
            await page.click("button:has-text('New')")
            await page.click("text=New folder")
            await page.fill("#folder-name-input", "Test Folder")
            await page.click("button:has-text('Create')")
            await page.wait_for_timeout(1000)

            # Check if folder is there
            content = await page.content()
            if "Test Folder" in content:
                print("Frontend E2E: Folder creation successful")
            else:
                print("Frontend E2E: Folder creation failed")

            await browser.close()

    finally:
        process.terminate()

asyncio.run(main())
