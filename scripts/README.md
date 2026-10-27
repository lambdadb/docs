# Public OpenAPI synchronization

`reference/api/openapi.json` is copied without transformation from the private
`lambdadb/lambdadb` repository's `api/openapi.json`. Do not edit it here. The
administrator specification is never an input to this workflow.

Fetch the server repository using your existing Git authentication, select an
exact commit, and confirm its public contract is deployed before synchronizing:

```sh
uv run --with-requirements tests/requirements.txt python -B scripts/sync_openapi.py \
  --server-repo /path/to/lambdadb --commit FULL_40_CHARACTER_COMMIT_SHA \
  --publication-evidence 'Deployment record or explicit production confirmation'
uv run --with-requirements tests/requirements.txt python -B scripts/sync_openapi.py \
  --check --server-repo /path/to/lambdadb
uv run --with-requirements tests/requirements.txt python -B -m unittest discover -s tests -v
```

Commit the spec and `reference/api/openapi-source.json` together. The record
contains source repository/path/commit, the exact byte SHA-256, and publication
evidence. Review that evidence; the script cannot infer deployment from a SHA.
The script reads the Git object, not a dirty working-tree file, and has no option
to select the admin path. It does not copy or log credentials.

For the initial ownership migration only, byte identity with the already public
docs spec at `94a7b71613a3bf217a370d5117b3ff6ddfbae851` is publication evidence.
This does not assert that the server source commit or other develop changes are
in production. Merge the server ownership PR before this dependent docs PR;
verify the pinned source remains reachable, and update the pin if the server PR
is squashed or rebased. Public API changes after migration require deployment
confirmation before docs promotion.

CI runs `--check` without accessing the private repository: it checks local
integrity and the public-path allowlist, not independent source authenticity.
Before submitting a sync, run the source-byte check above. The allowlist must be
reviewed explicitly before adding a new customer-facing path family; admin
routes must never be added to it. A guide-only PR does not need a spec sync.
