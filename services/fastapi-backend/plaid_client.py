import os
import plaid
from plaid.api import plaid_api

_client = None

_ENV_MAP = {
    "sandbox": plaid.Environment.Sandbox,
    "production": plaid.Environment.Production,
}


def get_plaid_client() -> plaid_api.PlaidApi:
    global _client
    if _client is None:
        env_name = os.environ.get("PLAID_ENV", "sandbox").lower()
        host = _ENV_MAP.get(env_name, plaid.Environment.Sandbox)
        configuration = plaid.Configuration(
            host=host,
            api_key={
                "clientId": os.environ["PLAID_CLIENT_ID"],
                "secret": os.environ["PLAID_SECRET"],
            }
        )
        _client = plaid_api.PlaidApi(plaid.ApiClient(configuration))
    return _client
