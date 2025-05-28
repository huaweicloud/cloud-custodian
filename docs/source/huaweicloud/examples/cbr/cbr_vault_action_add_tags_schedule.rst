policies:
  - name: cbr_vault_action_add_tags_schedule
    resource: huaweicloud.cbr-vault
    mode:
      type: huaweicloud-periodic
      xrole: fgs_admin
      eg_agency: EG_TARGET_AGENCY
      enable_lts_log: true
      schedule: "1h"
      schedule_type: Rate
    filters:
      - type: without_specific_tags
        keys: ['must-tag-key1', 'must-tag-key2']
    actions:
      - type: tag
        key: "must-tag-key1"
        value: "must-tag-value1"
      - type: tag
        key: "must-tag-key2"
        value: "must-tag-value2"