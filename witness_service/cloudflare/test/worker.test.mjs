import assert from "node:assert/strict";
import { createHash, generateKeyPairSync, sign, verify } from "node:crypto";
import test from "node:test";
import { handle } from "../worker.mjs";

class MemoryD1 {
  rows = [];
  prepare(query) {
    if (query.startsWith("SELECT")) {
      return { all: async () => ({ results: this.rows.map((row) => ({ row_json: JSON.stringify(row) })) }) };
    }
    return { bind: (...values) => ({ values }) };
  }
  async batch(statements) {
    const next = [...this.rows];
    for (const statement of statements) {
      const [ordinal, checkpointId, sequenceId, json] = statement.values;
      if (ordinal !== next.length + 1 || next.some((row) => row.checkpoint_id === checkpointId || row.sequence_id === sequenceId)) {
        throw new Error("UNIQUE constraint failed");
      }
      next.push(JSON.parse(json));
    }
    this.rows = next;
  }
}

const origin = generateKeyPairSync("ed25519");
const token = "a-long-random-access-token-for-tests-123456";
const readToken = "a-different-read-token-for-tests-1234567";

function checkpoint(id, hash = "a".repeat(64)) {
  const merkle_root = "b".repeat(64);
  return {
    checkpoint_id: id,
    sequence_id: id * 25,
    checkpoint_hash: hash,
    merkle_root,
    signature_hex: sign(null, Buffer.from(`${hash}:${merkle_root}`), origin.privateKey).toString("hex"),
    key_id: "local:ed25519:v1",
  };
}

function witness(name) {
  const key = generateKeyPairSync("ed25519");
  return {
    key,
    env: {
      DB: new MemoryD1(),
      WITNESS_NAME: name,
      WITNESS_PRIVATE_KEY_PEM: key.privateKey.export({ format: "pem", type: "pkcs8" }),
      ORIGIN_PUBLIC_KEY_PEM: origin.publicKey.export({ format: "pem", type: "spki" }),
      WITNESS_PUBLISH_TOKEN: token,
      WITNESS_READ_TOKEN: readToken,
    },
  };
}

async function call(env, method, path, rows, authorized = true) {
  const request = new Request(`https://witness.example${path}`, {
    method,
    headers: authorized ? { authorization: `Bearer ${method === "GET" ? readToken : token}` } : {},
    body: rows ? JSON.stringify({ checkpoints: rows }) : undefined,
  });
  const result = await handle(request, env);
  return { status: result.status, body: await result.json() };
}

test("two independent stores sign the same retained prefix and reject a fork", async () => {
  const first = witness("operator.one");
  const second = witness("operator.two");
  const rows = [checkpoint(1), checkpoint(2)];
  for (const instance of [first, second]) {
    assert.equal((await call(instance.env, "POST", "/v1/checkpoints", rows, false)).status, 401);
    const published = await call(instance.env, "POST", "/v1/checkpoints", rows);
    assert.equal(published.status, 200);
    const head = await call(instance.env, "GET", "/v1/head");
    assert.deepEqual(head.body.checkpoints, rows);
    const canonical = rows.map((row) => ({
      checkpoint_hash: row.checkpoint_hash, checkpoint_id: row.checkpoint_id,
      key_id: row.key_id, merkle_root: row.merkle_root,
      sequence_id: row.sequence_id, signature_hex: row.signature_hex,
    }));
    const prefix = Buffer.from(`argus.private-anchor-witness/v1\n${JSON.stringify(canonical)}`);
    assert.equal(head.body.prefix_sha256, createHash("sha256").update(prefix).digest("hex"));
    assert.ok(verify(null, prefix, instance.key.publicKey, Buffer.from(head.body.signature_hex, "hex")));
    assert.equal((await call(instance.env, "POST", "/v1/checkpoints", rows)).status, 200);
    assert.equal((await call(instance.env, "POST", "/v1/checkpoints", [rows[0]])).status, 409);
    assert.equal((await call(instance.env, "POST", "/v1/checkpoints", [checkpoint(1, "f".repeat(64)), rows[1]])).status, 409);
    const invalid = [{ ...rows[0], signature_hex: "0".repeat(128) }, rows[1]];
    assert.equal((await call(instance.env, "POST", "/v1/checkpoints", invalid)).status, 422);
    assert.deepEqual((await call(instance.env, "GET", "/v1/head")).body.checkpoints, rows);
  }
  assert.notEqual(first.env.DB, second.env.DB);
  assert.notEqual(first.key.privateKey.export({ format: "pem", type: "pkcs8" }).toString(),
                  second.key.privateKey.export({ format: "pem", type: "pkcs8" }).toString());
});
