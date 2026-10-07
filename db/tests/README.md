# Database test fixture data

Several legacy trigger and business-rule integration tests insert raw UTF-8
bytes into the historically named `*_encrypted` columns. Those rows are
deliberate legacy/adversarial fixtures used to exercise audit redaction,
immutability, and migration behavior. They are not supported employee write
paths and must only run against an isolated test database. New supported
employee writes, including seed and benchmark tools, must use
`db.crypto.pii.prepare_employee_pii` so both fields use the versioned AES-GCM
envelope and the audit trigger receives the matching blind index.

The SQL in `attack_demo_2.md` also includes a deliberately raw direct-SQL
fixture to demonstrate that a privileged writer can bypass application-layer
protections. It is an attack simulation, not an API insertion example.
