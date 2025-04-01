policies:
  - name: cbr_vault_action_add_tags
    resource: huaweicloud.cbr-vault
    filters:
      - 'tags': empty
    actions:
      - type: add_tags
        keys: ['test_key1', 'test_key2']
        values: ['test_value1', 'test_value2']
