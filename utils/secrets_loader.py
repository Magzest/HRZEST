# -*- coding: utf-8 -*-
"""AWS Secrets Manager loader -- populates os.environ before the app reads config.

Local/dev is unaffected: this is a no-op unless AWS_SECRET_ID is set, so
.env via python-dotenv remains the dev path. In production, set AWS_SECRET_ID
(and optionally AWS_REGION) as plain instance environment variables -- never
put the secret's *contents* in plaintext env vars, only its name/ARN.
"""
import os
import json
import logging

log = logging.getLogger("secrets_loader")


def load_aws_secrets(secret_id: str = None) -> bool:
    """Fetch a JSON secret from Secrets Manager and populate os.environ.

    Uses setdefault so already-set env vars (e.g. from a real .env in local
    dev) always win -- this only fills gaps. Returns True if secrets were
    loaded, False if skipped (no AWS_SECRET_ID configured).
    """
    secret_id = secret_id or os.environ.get("AWS_SECRET_ID")
    if not secret_id:
        return False

    import boto3
    from botocore.exceptions import BotoCoreError, ClientError

    region = os.environ.get("AWS_REGION", "ap-south-1")
    client = boto3.client("secretsmanager", region_name=region)
    try:
        resp = client.get_secret_value(SecretId=secret_id)
    except (BotoCoreError, ClientError) as exc:
        # Fail loudly rather than silently booting with missing secrets --
        # an attendance system with no ENCRYPTION_KEY would store PII in
        # plaintext with no warning otherwise (see utils/helpers.py).
        log.critical("Failed to load secrets from %s: %s", secret_id, exc)
        raise

    payload = json.loads(resp["SecretString"])
    for key, value in payload.items():
        os.environ.setdefault(key, value)
    log.info("Loaded %d secret(s) from %s", len(payload), secret_id)
    return True
