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

CLICKUP_HEADERS = {
    "Authorization": CLICKUP_API_TOKEN,
    "Content-Type": "application/json",
}

# AWS Bedrock
AWS_ACCESS_KEY: str       = os.environ["AWS_ACCESS_KEY"]
AWS_SECRET_KEY: str       = os.environ["AWS_SECRET_KEY"]
AWS_REGION: str           = os.environ.get("REGION")
AWS_BEDROCK_MODEL_ID: str = os.environ.get(
    "AWS_BEDROCK_MODEL_ID", "global.anthropic.claude-sonnet-4-6"
)

# Bitbucket
BITBUCKET_API_TOKEN: str     = os.environ["BITBUCKET_API_TOKEN"]
BITBUCKET_EMAIL: str         = os.environ.get("BITBUCKET_EMAIL", "")
BITBUCKET_WORKSPACE: str     = os.environ.get("BITBUCKET_WORKSPACE", "")
BITBUCKET_BASE_URL: str      = "https://api.bitbucket.org/2.0"

# Bitbucket uses HTTP Basic Auth with email:api_token as the credential pair.
def _bitbucket_auth() -> tuple[str, str]:
    """Return (email, token) credentials for Bitbucket HTTP Basic Auth."""
    return (BITBUCKET_EMAIL, BITBUCKET_API_TOKEN)

BITBUCKET_AUTH = _bitbucket_auth()

BITBUCKET_HEADERS = {
    "Content-Type": "application/json",
}
