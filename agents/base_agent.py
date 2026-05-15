import io
import json
import os
import sys
import httpx
from openai import OpenAI
from rich.console import Console

# Force UTF-8 on stdout/stderr before anything else writes to them
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

console = Console(file=io.StringIO(), highlight=False, markup=False, emoji=False)


def _log(msg: str):
    try:
        print(msg, flush=True)
    except Exception:
        pass

MODEL = os.getenv("OPENROUTER_MODEL", "google/gemini-2.5-pro-preview")

client = OpenAI(
    base_url="https://openrouter.ai/api/v1",
    api_key=os.getenv("OPENROUTER_API_KEY", ""),
    default_headers={"HTTP-Referer": "https://recruitingagents.vercel.app"},
)

PLATFORMS = {
    "AI Product Managers": [
        "LinkedIn", "Twitter/X", "Product Hunt", "Lenny's Newsletter Community",
        "Mind the Product", "ProductHunt", "Y Combinator community"
    ],
    "AI Designers": [
        "LinkedIn", "Dribbble", "Behance", "Twitter/X", "Figma Community",
        "Layers.to", "Designer Slack communities"
    ],
    "AI Engineers": [
        "GitHub", "HuggingFace", "LinkedIn", "Twitter/X", "ArXiv",
        "StackOverflow", "Discord AI communities", "Papers with Code"
    ],
    "Data Scientists": [
        "Kaggle", "LinkedIn", "GitHub", "ArXiv", "Twitter/X",
        "Towards Data Science", "Analytics Vidhya"
    ],
}

WEB_SEARCH_TOOL = {
    "type": "function",
    "function": {
        "name": "web_search",
        "description": (
            "Search the web for information. Use this to find candidate profiles "
            "on LinkedIn, GitHub, HuggingFace, Kaggle, Twitter/X, ArXiv, and other platforms."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "The search query",
                },
                "count": {
                    "type": "integer",
                    "description": "Number of results to return (1-10)",
                    "default": 5,
                },
            },
            "required": ["query"],
        },
    },
}


def _brave_search(query: str, count: int = 5) -> list[dict]:
    brave_key = os.getenv("BRAVE_API_KEY")
    if not brave_key:
        # Graceful degradation — model will work from its training knowledge
        return [{
            "title": "Web search unavailable",
            "url": "",
            "description": "BRAVE_API_KEY not configured. Using model knowledge only.",
        }]
    try:
        r = httpx.get(
            "https://api.search.brave.com/res/v1/web/search",
            headers={"X-Subscription-Token": brave_key},
            params={"q": query, "count": count},
            timeout=10,
        )
        r.raise_for_status()
        results = r.json().get("web", {}).get("results", [])
        return [
            {
                "title": item.get("title", ""),
                "url": item.get("url", ""),
                "description": item.get("description", ""),
            }
            for item in results
        ]
    except Exception as e:
        return [{"title": f"Search error: {e}", "url": "", "description": ""}]


def run_agent(
    system_prompt: str,
    user_message: str,
    tools: list[dict] | None = None,
    tool_handlers: dict | None = None,
    agent_name: str = "Agent",
) -> str:
    all_tools = [WEB_SEARCH_TOOL]
    if tools:
        all_tools.extend(tools)

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_message},
    ]

    _log(f"[{agent_name}] starting...")

    while True:
        response = client.chat.completions.create(
            model=MODEL,
            messages=messages,
            tools=all_tools,
        )

        choice = response.choices[0]
        msg = choice.message

        if choice.finish_reason == "tool_calls" and msg.tool_calls:
            messages.append({
                "role": "assistant",
                "content": msg.content,
                "tool_calls": [
                    {
                        "id": tc.id,
                        "type": "function",
                        "function": {
                            "name": tc.function.name,
                            "arguments": tc.function.arguments,
                        },
                    }
                    for tc in msg.tool_calls
                ],
            })

            for tool_call in msg.tool_calls:
                name = tool_call.function.name
                try:
                    args = json.loads(tool_call.function.arguments)
                except json.JSONDecodeError:
                    args = {}

                if name == "web_search":
                    result = _brave_search(args.get("query", ""), args.get("count", 5))
                elif tool_handlers and name in tool_handlers:
                    result = tool_handlers[name](args)
                else:
                    result = {"error": f"Unknown tool: {name}"}

                messages.append({
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": json.dumps(result),
                })

        else:
            _log(f"[{agent_name}] completed.")
            content = msg.content or ""
            content = content.replace(chr(0xFEFF), "").replace(chr(0xFFFE), "")
            return content
