import asyncio
import json
import os
import sys
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv
from playwright.async_api import async_playwright, Page
import openai

# Load environment variables
load_dotenv()

# Check for OpenAI API key
if not os.getenv("OPENAI_API_KEY"):
    print("Error: OPENAI_API_KEY environment variable not set.", file=sys.stderr)
    print("Please set it in your .env file or environment variables.", file=sys.stderr)
    sys.exit(1)

# Initialize OpenAI client
client = openai.AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

# JavaScript to inject to mark interactive elements and extract them
MARK_ELEMENTS_JS = """
() => {
    let elements = [];
    let idCounter = 1;

    // Selectors for interactive elements
    const selectors = 'a, button, input, select, textarea, [role="button"], [role="link"], [tabindex]:not([tabindex="-1"])';

    document.querySelectorAll(selectors).forEach(el => {
        // Skip hidden elements
        const rect = el.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0 || el.style.display === 'none' || el.style.visibility === 'hidden') {
            return;
        }

        // Skip elements that are disabled
        if (el.hasAttribute('disabled')) return;

        // Assign a unique ID if it doesn't have one
        const uniqueId = `llm-id-${idCounter++}`;
        el.setAttribute('data-llm-id', uniqueId);

        // Extract basic properties
        let text = el.innerText || el.value || el.placeholder || el.getAttribute('aria-label') || el.title || '';
        text = text.trim().substring(0, 50); // Limit text length

        let tagName = el.tagName.toLowerCase();
        let elementType = tagName;
        if (tagName === 'input') {
            elementType = `input[type="${el.type}"]`;
        }

        elements.push({
            id: uniqueId,
            type: elementType,
            text: text,
            role: el.getAttribute('role') || ''
        });

        // Visually highlight the element for debugging (optional)
        // el.style.outline = '2px solid red';
        // el.style.position = 'relative';

        // Add a small label (optional, can be disabled)
        // const label = document.createElement('div');
        // label.innerText = uniqueId;
        // label.style.position = 'absolute';
        // label.style.top = '0';
        // label.style.left = '0';
        // label.style.backgroundColor = 'red';
        // label.style.color = 'white';
        // label.style.fontSize = '10px';
        // label.style.padding = '1px';
        // label.style.zIndex = '10000';
        // el.appendChild(label);
    });

    return elements;
}
"""

async def extract_interactive_elements(page: Page) -> List[Dict[str, str]]:
    """Inject JS to mark interactive elements and return their details."""
    try:
        elements = await page.evaluate(MARK_ELEMENTS_JS)
        return elements
    except Exception as e:
        print(f"Error extracting elements: {e}")
        return []

async def get_next_action(objective: str, url: str, elements: List[Dict[str, str]], page_title: str) -> Dict[str, Any]:
    """Ask LLM to decide the next action based on the objective and current state."""

    # Format elements for the prompt
    elements_str = json.dumps(elements, indent=2)

    prompt = f"""
You are an autonomous web browser agent.
Your objective is: {objective}

CURRENT STATE:
Page Title: {page_title}
Current URL: {url}

INTERACTIVE ELEMENTS ON PAGE:
{elements_str}

Decide your next action to achieve the objective. You must output ONLY a JSON object with one of the following formats:

1. To go to a URL:
{{
  "action": "GOTO",
  "url": "https://example.com"
}}

2. To click an element (using its ID from the list above):
{{
  "action": "CLICK",
  "id": "llm-id-5"
}}

3. To type text into an input element:
{{
  "action": "TYPE",
  "id": "llm-id-8",
  "text": "Hello world"
}}

4. If you have achieved the objective or cannot proceed:
{{
  "action": "DONE",
  "reason": "Objective completed or stuck"
}}

Select the most logical next step. If an element has no text but the type/role suggests it's what you need, use it.
Provide ONLY the JSON response, no other text.
"""
    try:
        response = await client.chat.completions.create(
            model="gpt-4o-mini", # or "gpt-4-turbo" for better reasoning
            messages=[
                {"role": "system", "content": "You are a web automation assistant that outputs precise JSON instructions."},
                {"role": "user", "content": prompt}
            ],
            response_format={"type": "json_object"},
            temperature=0.1,
            max_tokens=150
        )

        result_text = response.choices[0].message.content
        return json.loads(result_text)
    except Exception as e:
        print(f"LLM Error: {e}")
        return {"action": "DONE", "reason": f"Error querying LLM: {str(e)}"}

async def execute_action(page: Page, action: Dict[str, Any]) -> bool:
    """Execute the action decided by the LLM."""
    action_type = action.get("action")
    print(f"\nExecuting: {action}")

    try:
        if action_type == "GOTO":
            await page.goto(action.get("url"), wait_until="networkidle")
            return True

        elif action_type == "CLICK":
            element_id = action.get("id")
            selector = f'[data-llm-id="{element_id}"]'
            # Wait a moment for element to be visible/clickable
            await page.wait_for_selector(selector, state="visible", timeout=5000)
            await page.click(selector)
            # Wait for any potential navigation or DOM updates
            await page.wait_for_timeout(2000)
            return True

        elif action_type == "TYPE":
            element_id = action.get("id")
            text = action.get("text")
            selector = f'[data-llm-id="{element_id}"]'
            await page.wait_for_selector(selector, state="visible", timeout=5000)
            await page.fill(selector, text)
            # Sometimes pressing Enter is needed after typing
            if action.get("press_enter", True):
                await page.press(selector, "Enter")
            await page.wait_for_timeout(2000)
            return True

        elif action_type == "DONE":
            print(f"Agent finished: {action.get('reason')}")
            return False

        else:
            print(f"Unknown action type: {action_type}")
            return False

    except Exception as e:
        print(f"Error executing action {action_type}: {e}")
        # Wait a bit on error before continuing
        await page.wait_for_timeout(2000)
        return True # Continue trying

async def run_agent(objective: str, start_url: str = "https://www.google.com", max_steps: int = 10):
    """Main loop to run the autonomous agent."""
    print(f"Starting agent with objective: '{objective}'")

    async with async_playwright() as p:
        # Launch browser (headless=False to see it working)
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 800},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = await context.new_page()

        # Navigate to start URL
        print(f"Navigating to {start_url}...")
        try:
            await page.goto(start_url, wait_until="networkidle", timeout=30000)
        except Exception as e:
            print(f"Initial navigation failed: {e}")
            await browser.close()
            return

        # Agent loop
        for step in range(max_steps):
            print(f"\n--- Step {step + 1}/{max_steps} ---")

            # Wait for page to settle
            await page.wait_for_timeout(2000)

            # Get current state
            current_url = page.url
            page_title = await page.title()

            # Extract elements
            print("Extracting interactive elements...")
            elements = await extract_interactive_elements(page)
            print(f"Found {len(elements)} interactive elements.")

            # If too many elements, we might need to filter them or chunk them
            # For this simple example, we'll just pass a subset if it's too large
            if len(elements) > 100:
                print("Too many elements, truncating for LLM context window...")
                elements = elements[:100]

            # Ask LLM for next action
            print("Asking LLM for next action...")
            action = await get_next_action(objective, current_url, elements, page_title)

            # Execute action
            continue_loop = await execute_action(page, action)

            if not continue_loop:
                break

        if step == max_steps - 1:
            print("Reached maximum steps without finishing.")

        print("Closing browser...")
        await browser.close()

if __name__ == "__main__":
    # Get objective from command line or use default
    if len(sys.argv) > 1:
        objective = " ".join(sys.argv[1:])
    else:
        objective = "Search for 'Playwright Python' on Google and click the first result"

    # Run the async loop
    asyncio.run(run_agent(objective))
