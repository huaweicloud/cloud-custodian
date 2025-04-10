policies:
    - name: cbr_vault_filter_tag_count
      resource: huaweicloud.cbr-vault
      filters:
        - type: tag-count
          op: ne
          count: 0

