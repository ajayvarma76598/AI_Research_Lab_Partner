import os
from dotenv import load_dotenv
from langfuse import Langfuse

load_dotenv()

_client: Langfuse = None


def get_langfuse_client() -> Langfuse:
    """
    Initialize Langfuse client using environment variables.
    """
    global _client
    if _client is not None:
        return _client

    secret_key = os.getenv("LANGFUSE_SECRET_KEY")
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")

    if not secret_key or not public_key:
        raise RuntimeError("LANGFUSE_SECRET_KEY and LANGFUSE_PUBLIC_KEY must be set in environment.")

    _client = Langfuse(secret_key=secret_key, public_key=public_key, host=host)
    return _client
