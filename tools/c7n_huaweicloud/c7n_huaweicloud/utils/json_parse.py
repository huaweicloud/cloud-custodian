import json


def safe_json_parse(response):
    if isinstance(response, dict):
        return response
    try:
        return json.loads(str(response))
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON format: {e}")
