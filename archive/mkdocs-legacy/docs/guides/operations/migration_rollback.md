# Rollback an authoritative migration

Use the rollback CLI to revert an authoritative migration by its
`migration_log_uid`.

## Usage

```bash
python -m calm.project.application.migration_rollback_cli /path/to/project <migration_log_uid>
```

## Example output

```json
{
  "migration_log_uid": "migration:abc123",
  "results": [
    {
      "prototype_uid": "proto:x",
      "status": "reverted",
      "reason": null,
      "updated_uid": null
    }
  ]
}
```

## Notes and limitations

- Rollback applies only to authoritative migrations with recorded migration history.
- The project must be filesystem-backed (a local `.calm` directory / SQLite database).
- A rollback may partially succeed if some prototype history is incomplete.
- Avoid concurrent writes while running rollback.
