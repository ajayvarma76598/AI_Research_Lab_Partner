import logging
from config import get_llm
from langfuse import Langfuse
from langfuse.decorators import observe

logger = logging.getLogger(__name__)
langfuse_client = Langfuse()

@observe(as_type="span", name="prompt_injection_firewall")
def check_prompt_injection(text: str) -> bool:
    """
    Checks if the input text contains a prompt injection attack.
    Returns True if malicious, False if safe.
    """
    try:
        llm = get_llm()
        lf_prompt = langfuse_client.get_prompt("security_firewall")
        prompt = lf_prompt.compile(text=text)
        
        response = llm.complete(prompt)
        result = response.text.strip().upper()
        
        if "MALICIOUS" in result:
            logger.warning(f"Prompt injection detected! Blocked text: {text}")
            return True
        return False
    except Exception as e:
        logger.error(f"Firewall check failed: {e}")
        # Fail-open or fail-closed? Let's fail-open to not break the app on Langfuse errors
        return False
