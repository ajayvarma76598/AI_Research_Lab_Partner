import os
from sqlalchemy import text
from dotenv import load_dotenv
load_dotenv()
from db.models import get_engine
import sys
import os

# Add current directory to path so db.models works
sys.path.append(os.path.dirname(__file__))

engine = get_engine()
with engine.connect() as conn:
    print("Dropping NOT NULL constraint from document_id in chat_sessions...")
    conn.execute(text("ALTER TABLE chat_sessions ALTER COLUMN document_id DROP NOT NULL;"))
    conn.commit()
    print("Migration complete!")
