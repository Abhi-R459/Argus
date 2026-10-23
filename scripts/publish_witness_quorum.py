"""Scheduled submission of PII-free checkpoints to independent witnesses.

The job uses only the read-only Auditor database role. It has neither the
origin signing key nor administrative access to the witness databases.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
import re
import sys

import httpx
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
from cryptography.hazmat.primitives.serialization import load_pem_public_key
from sqlalchemy.engine import make_url
import psycopg2

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from api.services.remote_anchor import checkpoint_row  # noqa: E402
from api.services.remote_witness import checkpoint_prefix_bytes  # noqa: E402
from api.services.independent_witnesses import fetch_witness_head, validate_services  # noqa: E402
from api.services.checkpoint_binding import verify_checkpoint_bindings  # noqa: E402
from db.cli.hash_verifier import verify_chain  # noqa: E402


async def database_checkpoints(url: str) -> list[dict]:
    def read_and_verify() -> list[dict]:
        parsed = make_url(url).set(drivername="postgresql")
        query = dict(parsed.query)
        if "ssl" in query:
            if "sslmode" in query:
                raise ValueError("Conflicting database TLS settings.")
            query["sslmode"] = query.pop("ssl")
        dsn = parsed.set(query=query).render_as_string(hide_password=False)
        connection = psycopg2.connect(dsn, connect_timeout=8,
                                       options="-c statement_timeout=30000 -c lock_timeout=5000")
        try:
            connection.set_session(isolation_level="REPEATABLE READ", readonly=True)
            with connection.cursor() as cursor:
                cursor.execute("SELECT current_user")
                if str(cursor.fetchone()[0]).split(".")[0] != "compliance_auditor":
                    raise ValueError("Only the read-only compliance_auditor role may publish.")
                chain = verify_chain(connection)
                binding = verify_checkpoint_bindings(connection)
                if not chain.is_valid or binding.status != "pass":
                    raise ValueError("The audit chain or checkpoint bindings failed verification.")
                cursor.execute("SELECT enabled, interval_events FROM checkpoint_schedule_settings WHERE id = 1")
                schedule = cursor.fetchone()
                cursor.execute("SELECT checkpoint_id, sequence_id, checkpoint_hash, merkle_root, signature, key_id "
                               "FROM chain_checkpoints ORDER BY sequence_id")
                rows = cursor.fetchall()
            checkpoints = [checkpoint_row(*row) for row in rows]
            if schedule and schedule[0]:
                interval = int(schedule[1])
                completed = [row["sequence_id"] for row in checkpoints if row["sequence_id"] % interval == 0]
                if not completed:
                    return []
                checkpoints = [row for row in checkpoints if row["sequence_id"] <= completed[-1]]
            if len(checkpoints) > 1000:
                raise ValueError("The witness prefix limit was reached; archival is required.")
            return checkpoints
        finally:
            connection.close()
    return await asyncio.to_thread(read_and_verify)


def verify_origin(checkpoints: list[dict], origin_pem: str) -> None:
    key = load_pem_public_key(origin_pem.encode("utf-8"))
    if not isinstance(key, Ed25519PublicKey):
        raise ValueError("The origin key must be Ed25519.")
    previous_id = previous_sequence = 0
    for row in checkpoints:
        if (row["checkpoint_id"] <= previous_id or row["sequence_id"] <= previous_sequence
                or row["checkpoint_id"] > 2**53 - 1 or row["sequence_id"] > 2**53 - 1
                or not isinstance(row["key_id"], str)
                or not re.fullmatch(r"[A-Za-z0-9._:/%-]{1,120}", row["key_id"])):
            raise ValueError("Checkpoint order is invalid.")
        key.verify(bytes.fromhex(row["signature_hex"]),
                   f'{row["checkpoint_hash"]}:{row["merkle_root"]}'.encode("utf-8"))
        previous_id, previous_sequence = row["checkpoint_id"], row["sequence_id"]


async def publish_once(*, database_url: str, origin_pem: str, services_raw: str,
                       trust_raw: str, client: httpx.AsyncClient) -> str:
    services = validate_services(services_raw, trust_raw, origin_pem)
    trust = json.loads(trust_raw)
    checkpoints = await database_checkpoints(database_url)
    if not checkpoints:
        return "No completed signed checkpoint is ready."
    verify_origin(checkpoints, origin_pem)
    payload = checkpoint_prefix_bytes(checkpoints, len(checkpoints) - 1)
    expected_digest = hashlib.sha256(payload).hexdigest()
    for service in services:
        endpoint = service["url"].rstrip("/")
        headers = {"Authorization": f'Bearer {service["token"]}'}
        submitted = await client.post(f"{endpoint}/v1/checkpoints", headers=headers,
                                      json={"checkpoints": checkpoints}, follow_redirects=False)
        submitted.raise_for_status()
        receipt = await fetch_witness_head(client, endpoint, service["token"])
        if (receipt.get("schema_version") != 1 or receipt.get("name") != service["name"]
                or receipt.get("checkpoints") != checkpoints
                or receipt.get("prefix_sha256") != expected_digest):
            raise ValueError("Witness readback does not match the submitted checkpoint prefix.")
        signature_hex = receipt.get("signature_hex")
        if not isinstance(signature_hex, str) or not re.fullmatch(r"[0-9a-f]{128}", signature_hex):
            raise ValueError("Witness signature is malformed.")
        key = load_pem_public_key(trust[service["name"]]["public_key_pem"].encode("utf-8"))
        key.verify(bytes.fromhex(signature_hex), payload)
    return f'{len(services)} witnesses retained checkpoint sequence {checkpoints[-1]["sequence_id"]}.'


async def _main() -> None:
    async with httpx.AsyncClient(timeout=15.0, trust_env=False) as client:
        message = await publish_once(
            database_url=os.environ["DATABASE_URL_COMPLIANCE_AUDITOR"],
            origin_pem=os.environ["ORIGIN_PUBLIC_KEY_PEM"],
            services_raw=os.environ["WITNESS_PUBLISH_ENDPOINTS_JSON"],
            trust_raw=os.environ["WITNESS_TRUST_CONFIG_JSON"],
            client=client,
        )
    print(message)


if __name__ == "__main__":
    asyncio.run(_main())
