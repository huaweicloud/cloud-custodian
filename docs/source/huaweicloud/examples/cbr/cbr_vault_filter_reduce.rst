policies:
    - name: cbr_vault_filter_reduce
      resource: huaweicloud.cbr-vault
      filters:
        - type: reduce
          sort-by: created_at
          order: asc

