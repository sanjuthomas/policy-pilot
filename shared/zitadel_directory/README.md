"""Shared ZITADEL user-directory client.

Used by authorization-service, ssi-chat, and ssi-demo-harness to list human users
and hydrate custom metadata (`roles`, `groups`, `covering_lobs`, …).

`zitadel-seed/users.yaml` remains the seed source; this package is the runtime
directory reader.
"""
