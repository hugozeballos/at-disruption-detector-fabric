"""
Option A: read the secrets from Azure Key Vault instead of a Lakehouse.

Only the secret-reading part and the decorators change. Copy this block over the
`read_secrets` function and the `get_at_realtime` entry point in get_at_realtime.py;
`flatten_trip_update` and `poll_and_send` stay the same.

Setup:
  - Key Vault secrets: at-subscription-key, eventhub-connection-string
  - IAM on the vault: "Key Vault Secrets User" for the account that runs the function
  - Library management: azure-eventhub, azure-keyvault-secrets
  - Manage connections: a connection to the Key Vault

Note: the version that ran in this project read only the AT key from Key Vault;
reading the connection string the same way uses the same mechanism but was not tested.
"""

import fabric.functions as fn
from azure.keyvault.secrets import SecretClient

udf = fn.UserDataFunctions()

KEY_VAULT_URL = "https://<your-vault-name>.vault.azure.net/"


@udf.generic_connection(argName="keyVaultClient", audienceType="KeyVault")
@udf.function()
def get_at_realtime(keyVaultClient: fn.FabricItem) -> str:
    credential = keyVaultClient.get_access_token()
    secrets = SecretClient(vault_url=KEY_VAULT_URL, credential=credential)
    at_subscription_key = secrets.get_secret("at-subscription-key").value
    connection_str = secrets.get_secret("eventhub-connection-string").value
    return poll_and_send(at_subscription_key, connection_str)  # noqa: F821 (defined in get_at_realtime.py)
