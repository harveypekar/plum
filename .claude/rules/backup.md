# Backup Rules

## Encryption Requirement (Non-Negotiable)

- **Never** use the bare `hetzner:` rclone remote for transfers — always use `hetzner-crypt:`
- All data sent to Hetzner Storage Box must be encrypted both in transit (SFTP) and at rest (rclone crypt)
- The backup config at `projects/backup/backup-dirs.json` has `require_encrypted_remote: true` — any backup script must verify the remote type is `crypt` before transferring
- If `BACKUP_RCLONE_REMOTE` in `.env` does not match the `remote` field in the config, abort
