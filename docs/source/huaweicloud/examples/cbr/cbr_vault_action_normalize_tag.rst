policies:
    - name: cbr_vault_action_normalize_tag
      resource: huaweicloud.cbr-vault
      actions:
        - type: normalize-tag
          key: new_test_key1
          action: upper
