policies:
- name: enable-stack-deletion-protection
  resource: huaweicloud.rfs-stack
  filters:
    - type: value
      key: enable_deletion_protection
      value: true
  actions:
    - enable_deletion_protection
