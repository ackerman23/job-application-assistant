import json
from app.core.config import OPENAI_API_KEY, OPENAI_MODEL


def complete_json(system_prompt: str, payload: dict) -> dict:
    """Request a JSON object from the configured model without logging candidate data."""
    if not OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY is not configured")
    from openai import OpenAI
    response = OpenAI(api_key=OPENAI_API_KEY).chat.completions.create(
        model=OPENAI_MODEL,
        temperature=0.1,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
        ],
    )
    content = response.choices[0].message.content
    if not content:
        raise ValueError("The AI returned an empty response.")
    value = json.loads(content)
    if not isinstance(value, dict):
        raise ValueError("The AI response was not a JSON object.")
    return value
