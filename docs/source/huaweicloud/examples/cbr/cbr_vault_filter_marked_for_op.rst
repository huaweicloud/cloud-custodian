policies:
  - name: cbr_vault_filter_marked_for_op
    resource: huaweicloud.cbr-vault
    filters:
      - type: marked-for-op
        tag: custodian_status
        op: webhook
        skew: 4
        skew_hours: 2
