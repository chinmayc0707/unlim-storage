# LLM Browser Agent

An autonomous web browser agent that uses LLMs (like OpenAI's GPT-4o-mini) and Playwright to navigate websites, click elements, and type text based on a high-level objective.

## Setup

1. Install dependencies:
   ```bash
   pip install -r requirements.txt
   playwright install chromium
   ```

2. Set up your environment variables by creating a `.env` file:
   ```bash
   # .env
   OPENAI_API_KEY=your_openai_api_key_here
   ```

## Usage

Run the agent with an objective:

```bash
python browser_agent.py "Search for 'Playwright Python' on Google and click the first result"
```

## How it works

1. It navigates to a starting page (Google by default).
2. It injects JavaScript to find all interactive elements (links, buttons, inputs) and assigns them unique IDs.
3. It sends the list of elements along with the current page state to the LLM.
4. The LLM decides the next action (GOTO, CLICK, TYPE, or DONE).
5. Playwright executes the action.
6. The process repeats until the objective is reached.
