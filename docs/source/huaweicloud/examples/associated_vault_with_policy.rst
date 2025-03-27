policies:
    - name: associate_vault_policy_unprotected
      resource: huaweicloud.cbr-vault
      filters:
        - and:
          - type: unassociated
          - type: value
            key: billing.protect_type
            value: "backup"
      actions:
        - type: associate_vault_policy
          day_backups: 0
          week_backups: 0
          month_backups: 0
          year_backups: 0
          max_backups: -1
          retention_duration_days: 30
          full_backup_interval: -1
          timezone: "UTC+08:00"
