policies:
  - name: cbr_vault_filter_unassociated_with_policy
    resource: huaweicloud.cbr-vault
    filters:
      - and:
        - type: unassociated
        - type: value
          key: billing.protect_type
          value: "backup"
