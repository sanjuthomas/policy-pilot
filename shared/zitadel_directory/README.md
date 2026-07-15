"""Shared ZITADEL user-directory client.

Used by authorization-service, ssi-chat, and ssi-demo-harness to list human users
and hydrate custom metadata (`roles`, `groups`, `covering_lobs`, …).

`zitadel-seed/users.yaml` remains the seed source; this package is the runtime
directory reader.

## API

- `build_directory_client(...)` — single place for PAT/base URL + optional org header
- `ZitadelDirectoryClient.list_directory_users()` — hydrate `DirectoryUser` rows
- `DirectoryCache` — shared TTL cache over `list_directory_users`
- `DirectoryUser.seed_fields()` — map into service-local SeedUser models

Services should not re-implement client construction, `with_org` fallback, or
directory TTL caching.
"""
