SUPPORTED_WEBSITES = [
    {
        "app_name": "YouTube",
        "app_id": "youtube",
        "url": "https://www.youtube.com",
        "aliases": ["you tube"]
    },
    {
        "app_name": "ChatGPT",
        "app_id": "chatgpt",
        "url": "https://chatgpt.com",
        "aliases": ["chat gpt"]
    }
]


def get_supported_websites():
    """Return the supported website catalogue."""
    return SUPPORTED_WEBSITES