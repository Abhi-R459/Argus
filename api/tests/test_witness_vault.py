"""A witness's private key stays encrypted in that operator's own vault."""

from cryptography.hazmat.primitives.serialization import load_pem_public_key

from scripts.cosign_private_anchor import _load_witness_key
from scripts.init_witness_vault import initialize_vault


def test_operator_vault_encrypts_key_and_refuses_reuse(tmp_path, monkeypatch):
    vault = initialize_vault("auditor.one", tmp_path / "operator-home", "correct horse battery staple")
    private_bytes = (vault / "private.pem").read_bytes()
    assert b"ENCRYPTED PRIVATE KEY" in private_bytes
    assert (vault / "public.pem").is_file()
    monkeypatch.setattr("scripts.cosign_private_anchor.getpass.getpass", lambda _: "correct horse battery staple")
    private_key = _load_witness_key(vault / "private.pem")
    public_key = load_pem_public_key((vault / "public.pem").read_bytes())
    payload = b"separately retained checkpoint"
    public_key.verify(private_key.sign(payload), payload)
    try:
        initialize_vault("auditor.one", tmp_path / "operator-home", "correct horse battery staple")
    except FileExistsError:
        pass
    else:
        raise AssertionError("Existing witness vault was overwritten")
