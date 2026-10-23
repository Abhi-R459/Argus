import { createHash, sign, timingSafeEqual, verify } from "node:crypto";

const fields = ["checkpoint_id", "sequence_id", "checkpoint_hash", "merkle_root", "signature_hex", "key_id"];
const hex64 = /^[0-9a-f]{64}$/;
const hex128 = /^[0-9a-f]{128}$/;
const encoder = new TextEncoder();

function response(body, status = 200) {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "content-type": "application/json", "cache-control": "no-store" },
  });
}

function authorized(request, token) {
  const actual = encoder.encode(request.headers.get("authorization") || "");
  const expected = encoder.encode(`Bearer ${token}`);
  return expected.length >= 39 && actual.length === expected.length && timingSafeEqual(actual, expected);
}

function canonicalRow(value, priorId, priorSequence, originKey) {
  if (!value || typeof value !== "object" || Array.isArray(value) ||
      Object.keys(value).length !== fields.length || fields.some((field) => !(field in value))) {
    throw new Error("Checkpoint fields are invalid.");
  }
  const row = {
    checkpoint_hash: value.checkpoint_hash,
    checkpoint_id: value.checkpoint_id,
    key_id: value.key_id,
    merkle_root: value.merkle_root,
    sequence_id: value.sequence_id,
    signature_hex: value.signature_hex,
  };
  if (!Number.isSafeInteger(row.checkpoint_id) || row.checkpoint_id <= priorId ||
      !Number.isSafeInteger(row.sequence_id) || row.sequence_id <= priorSequence ||
      !hex64.test(row.checkpoint_hash) || !hex64.test(row.merkle_root) ||
      !hex128.test(row.signature_hex) || typeof row.key_id !== "string" ||
      !/^[A-Za-z0-9._:/%-]{1,120}$/.test(row.key_id)) {
    throw new Error("Checkpoint data or order is invalid.");
  }
  if (!verify(null, Buffer.from(`${row.checkpoint_hash}:${row.merkle_root}`), originKey,
              Buffer.from(row.signature_hex, "hex"))) {
    throw new Error("Origin signature is invalid.");
  }
  return row;
}

function prefixBytes(rows) {
  return Buffer.from(`argus.private-anchor-witness/v1\n${JSON.stringify(rows)}`);
}

function receipt(name, rows, privateKey) {
  if (!rows.length) {
    return { schema_version: 1, name, checkpoints: [], signature_hex: null, prefix_sha256: null };
  }
  const payload = prefixBytes(rows);
  return {
    schema_version: 1,
    name,
    checkpoints: rows,
    signature_hex: sign(null, payload, privateKey).toString("hex"),
    prefix_sha256: createHash("sha256").update(payload).digest("hex"),
  };
}

async function storedRows(db) {
  const result = await db.prepare("SELECT row_json FROM checkpoints ORDER BY ordinal").all();
  return result.results.map(({ row_json }) => JSON.parse(row_json));
}

export async function handle(request, env) {
  if (!env.DB || !env.WITNESS_NAME || !env.WITNESS_PRIVATE_KEY_PEM ||
      !env.ORIGIN_PUBLIC_KEY_PEM || !env.WITNESS_READ_TOKEN || !env.WITNESS_PUBLISH_TOKEN) {
    return response({ detail: "Witness is not configured." }, 503);
  }
  const path = new URL(request.url).pathname;
  const expectedToken = request.method === "GET" && path === "/v1/head"
    ? env.WITNESS_READ_TOKEN : env.WITNESS_PUBLISH_TOKEN;
  if (!authorized(request, expectedToken)) {
    return response({ detail: "Unauthorized" }, 401);
  }
  if (request.method === "GET" && path === "/v1/head") {
    return response(receipt(env.WITNESS_NAME, await storedRows(env.DB), env.WITNESS_PRIVATE_KEY_PEM));
  }
  if (request.method !== "POST" || path !== "/v1/checkpoints") {
    return response({ detail: "Not found" }, 404);
  }
  const length = Number(request.headers.get("content-length") || "0");
  if (length > 1_000_000) return response({ detail: "Request is too large." }, 413);
  const raw = await request.text();
  if (encoder.encode(raw).length > 1_000_000) return response({ detail: "Request is too large." }, 413);
  let proposed;
  try {
    const body = JSON.parse(raw);
    if (!body || Object.keys(body).length !== 1 || !Array.isArray(body.checkpoints) ||
        body.checkpoints.length < 1 || body.checkpoints.length > 1000) {
      throw new Error("Checkpoint list is invalid.");
    }
    proposed = body.checkpoints;
  } catch {
    return response({ detail: "Checkpoint submission is invalid." }, 422);
  }
  const existing = await storedRows(env.DB);
  if (proposed.length < existing.length) {
    return response({ detail: "Previously witnessed history cannot be removed." }, 409);
  }
  let verified;
  try {
    verified = [];
    let priorId = 0, priorSequence = 0;
    for (const value of proposed) {
      const row = canonicalRow(value, priorId, priorSequence, env.ORIGIN_PUBLIC_KEY_PEM);
      verified.push(row);
      priorId = row.checkpoint_id;
      priorSequence = row.sequence_id;
    }
  } catch {
    return response({ detail: "Checkpoint submission is invalid." }, 422);
  }
  for (let index = 0; index < existing.length; index += 1) {
    if (JSON.stringify(verified[index]) !== JSON.stringify(existing[index])) {
      return response({ detail: "Previously witnessed checkpoint history changed." }, 409);
    }
  }
  try {
    const additions = verified.slice(existing.length).map((row, index) =>
      env.DB.prepare("INSERT INTO checkpoints (ordinal, checkpoint_id, sequence_id, row_json) VALUES (?, ?, ?, ?)")
        .bind(existing.length + index + 1, row.checkpoint_id, row.sequence_id, JSON.stringify(row)));
    if (additions.length) await env.DB.batch(additions);
    // A concurrent conflicting insert must never receive a signature.
    const retained = await storedRows(env.DB);
    if (JSON.stringify(retained) !== JSON.stringify(verified)) {
      return response({ detail: "Witness state changed concurrently." }, 409);
    }
    return response(receipt(env.WITNESS_NAME, retained, env.WITNESS_PRIVATE_KEY_PEM));
  } catch (error) {
    if (error instanceof Error && (error.message.includes("UNIQUE") || error.message.includes("constraint"))) {
      return response({ detail: "Witness state changed concurrently." }, 409);
    }
    return response({ detail: "Witness state is unavailable." }, 503);
  }
}

export default { fetch: handle };
