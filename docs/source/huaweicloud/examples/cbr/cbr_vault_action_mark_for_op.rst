policies:
  - name: cbr_vault_action_mark_for_op
    resource: huaweicloud.cbr-vault
    filters:
      - type: tag-count
        op: equal
        count: 0
    actions:
      - type: mark-for-op
        tag: custodian_status
        op: webhook
        days: 4