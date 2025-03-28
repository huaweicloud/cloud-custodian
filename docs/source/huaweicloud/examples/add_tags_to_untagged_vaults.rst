policies:
- name: add_tag_vault_untagged
  resource: huaweicloud.cbr-vault
  filters:
    - 'tags': empty
  actions:
    - type: add_tags
      keys: ['1', '2']
      values: ['1', '2']
