"""
Fabric User Data Function: polls Auckland Transport's GTFS-Realtime feed,
keeps only trip updates, flattens them and sends them to an Eventstream.

Secrets: option B (private Lakehouse) is used below.
For option A (Azure Key Vault), see udf/get_at_realtime_keyvault.py.

Setup in Fabric:
  - Library management: azure-eventhub
  - Manage connections: Lakehouse `lh_secrets`, alias `lhsecrets`
  - Files in the Lakehouse: Files/secrets/at_subscription_key.txt
                            Files/secrets/eventhub_connection_str.txt
"""

import fabric.functions as fn
import requests
import json
from datetime import datetime, timezone
from azure.eventhub import EventHubProducerClient, EventData

udf = fn.UserDataFunctions()

AT_KEY_PATH = "secrets/at_subscription_key.txt"
EVENTHUB_CONN_PATH = "secrets/eventhub_connection_str.txt"
EVENTHUB_NAME = "<your-event-hub-name>"  # not a secret; shown in the Eventstream source
AT_KEY_LENGTH = 32
AT_FEED_URL = "https://api.at.govt.nz/realtime/legacy/"


def read_secrets(lakehouse: fn.FabricLakehouseClient) -> tuple[str, str]:
    """Read the AT key and the Event Hub connection string from lh_secrets.
    Validates their format without printing them."""
    connection = lakehouse.connectToFiles()
    try:
        values = []
        for path in (AT_KEY_PATH, EVENTHUB_CONN_PATH):
            file_client = connection.get_file_client(path)
            # utf-8-sig drops the byte-order mark that Windows Notepad may add
            values.append(file_client.download_file().readall().decode("utf-8-sig").strip())
            file_client.close()
    finally:
        connection.close()

    at_key, conn_str = values
    if len(at_key) != AT_KEY_LENGTH:
        raise ValueError(f"Invalid AT key: length {len(at_key)}, expected {AT_KEY_LENGTH}")
    if not (conn_str.startswith("Endpoint=sb://") and "SharedAccessKey=" in conn_str):
        raise ValueError("Event Hub connection string has an invalid format")
    return at_key, conn_str


def flatten_trip_update(entity: dict, ingestion_ts: str) -> dict | None:
    """Flatten a trip_update entity into the 9 columns of at_stop_updates_raw.
    Returns None for anything else (vehicle positions, alerts)."""
    trip_update = entity.get("trip_update")
    if trip_update is None:
        return None

    trip = trip_update.get("trip", {})
    stop_time_update = trip_update.get("stop_time_update", {})
    vehicle = trip_update.get("vehicle", {})

    feed_timestamp_epoch = trip_update.get("timestamp")
    feed_timestamp_iso = (
        datetime.fromtimestamp(feed_timestamp_epoch, tz=timezone.utc).isoformat()
        if feed_timestamp_epoch is not None else None
    )

    return {
        "trip_id": trip.get("trip_id"),
        "route_id": trip.get("route_id"),
        "stop_id": stop_time_update.get("stop_id"),
        "vehicle_id": vehicle.get("id"),
        "arrival_delay_seconds": stop_time_update.get("arrival", {}).get("delay"),
        "departure_delay_seconds": stop_time_update.get("departure", {}).get("delay"),
        "schedule_relationship": trip.get("schedule_relationship"),
        "feed_timestamp": feed_timestamp_iso,
        "ingestion_timestamp": ingestion_ts,
    }


def poll_and_send(at_subscription_key: str, connection_str: str) -> str:
    """Poll the AT feed once and send the flattened trip updates to the Eventstream."""
    headers = {"Ocp-Apim-Subscription-Key": at_subscription_key}
    response = requests.get(AT_FEED_URL, headers=headers, timeout=30)
    response.raise_for_status()  # fail loudly on a rejected key instead of sending 0 events
    data = response.json()

    entities = data.get("response", {}).get("entity", [])
    ingestion_ts = datetime.now(timezone.utc).isoformat()  # one timestamp per poll

    producer = EventHubProducerClient.from_connection_string(
        conn_str=connection_str, eventhub_name=EVENTHUB_NAME
    )
    event_batch = producer.create_batch()

    sent_count = 0
    skipped_count = 0
    for entity in entities:
        flat_event = flatten_trip_update(entity, ingestion_ts)
        if flat_event is None:
            skipped_count += 1
            continue

        event_json = json.dumps(flat_event)
        try:
            event_batch.add(EventData(event_json))
        except ValueError:  # batch full: send it and start a new one
            producer.send_batch(event_batch)
            event_batch = producer.create_batch()
            event_batch.add(EventData(event_json))
        sent_count += 1

    if len(event_batch) > 0:
        producer.send_batch(event_batch)

    producer.close()
    return f"Sent {sent_count} flat events (skipped {skipped_count} non-trip_update)"


@udf.connection(argName="secretsLakehouse", alias="lhsecrets")
@udf.function()
def get_at_realtime(secretsLakehouse: fn.FabricLakehouseClient) -> str:
    at_subscription_key, connection_str = read_secrets(secretsLakehouse)
    return poll_and_send(at_subscription_key, connection_str)
