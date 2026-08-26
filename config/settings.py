"""
config/settings.py
Centralised environment variable loading.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# ClickUp
CLICKUP_API_TOKEN: str = os.environ["CLICKUP_API_TOKEN"]
CLICKUP_BASE_URL: str  = "https://api.clickup.com/api/v2"

# AWS Bedrock
AWS_ACCESS_KEY: str       = os.environ["AWS_ACCESS_KEY"]
AWS_SECRET_KEY: str       = os.environ["AWS_SECRET_KEY"]
AWS_REGION: str           = os.environ.get("REGION")
AWS_BEDROCK_MODEL_ID: str = os.environ.get(
    "AWS_BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-6"
)

CLICKUP_HEADERS = {
    "Authorization": CLICKUP_API_TOKEN,
    "Content-Type": "application/json",
}
