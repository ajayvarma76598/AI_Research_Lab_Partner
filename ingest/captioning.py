import logging
import os
import base64
from pathlib import Path
from typing import Optional

from openai import AzureOpenAI as AzureOpenAIClient
from dotenv import load_dotenv

logger = logging.getLogger(__name__)
load_dotenv()

MIME_TYPE_MAP = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
}


def generate_caption(image_path: str, prompt: Optional[str] = None) -> str:
    """
    Generate a caption/insight for a figure image using the vision model.
    """
    if prompt is None:
        prompt = (
            "Describe the content and research insight of this figure/chart in "
            "2-3 concise sentences. Focus on what data or result it conveys."
        )

    with open(image_path, "rb") as image_file:
        image_bytes = image_file.read()
        image_data = base64.b64encode(image_bytes).decode("utf-8")

    ext = Path(image_path).suffix.lower()
    mime_type = MIME_TYPE_MAP.get(ext, "image/png")

    client = AzureOpenAIClient(
        api_key=os.environ.get("AZURE_OPENAI_API_KEY"),
        azure_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT"),
        api_version=os.environ.get("AZURE_OPENAI_API_VERSION", "2024-02-15-preview"),
    )
    deployment = os.environ.get("AZURE_OPENAI_LLM_DEPLOYMENT")

    response = client.chat.completions.create(
        model=deployment,
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {
                        "type": "image_url",
                        "image_url": {"url": f"data:{mime_type};base64,{image_data}"},
                    },
                ],
            }
        ],
        max_tokens=200,
    )

    caption = response.choices[0].message.content.strip()
    logger.info(f"Generated caption for {image_path}: {caption[:80]}...")
    return caption
