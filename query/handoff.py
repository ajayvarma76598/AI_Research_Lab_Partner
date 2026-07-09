import logging
import os
import smtplib
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


def send_handoff_email(query_id: str, question: str, answer: str, faithfulness: float, relevance: float, confidence: float):
    """Send an escalation email to the support reviewer inbox."""
    smtp_host = os.getenv("SMTP_HOST")
    smtp_port = int(os.getenv("SMTP_PORT", 587))
    smtp_username = os.getenv("SMTP_USERNAME")
    smtp_password = os.getenv("SMTP_PASSWORD")
    support_email = os.getenv("SUPPORT_EMAIL")
    application_email = os.getenv("APPLICATION_EMAIL")

    if not all([smtp_host, smtp_username, smtp_password, support_email]):
        logger.warning("SMTP not fully configured - skipping handoff email (would have escalated)")
        return False

    body = f"""
    A query was escalated for human review after failing SLO checks 3 times.

    Query ID: {query_id}
    Question: {question}
    Last draft answer: {answer}

    Scores:
      Faithfulness: {faithfulness}
      Relevance: {relevance}
      Confidence: {confidence}
    """

    msg = MIMEText(body)
    msg["Subject"] = f"[Research Lab Partner] Query escalation - {query_id}"
    msg["From"] = application_email or smtp_username
    msg["To"] = support_email

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as server:
            server.starttls()
            server.login(smtp_username, smtp_password)
            server.send_message(msg)
        logger.info(f"Handoff email sent for query_id={query_id}")
        return True
    except Exception as e:
        logger.error(f"Failed to send handoff email: {e}")
        return False
