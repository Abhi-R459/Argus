# Supabase database CA

`supabase-ca.crt` is a public CA certificate downloaded through the Argus Supabase dashboard's Database Settings → SSL configuration on 11 October 2026.

Source: https://supabase-downloads.s3-ap-southeast-1.amazonaws.com/prod/ssl/prod-ca-2021.crt

SHA-256 certificate fingerprint: `807025ad50d4ed219d2c9c7d299c004f824eb00cf7f65afef607d07b72e6cafa`

Certificate validity ends on 26 April 2031. Verify the current provider certificate before replacing this trust root. This file contains no private key or account credentials. The API image includes it at `/app/certificates/supabase-ca.crt`; production database URLs select it using `sslrootcert` and `sslmode=verify-full`.
