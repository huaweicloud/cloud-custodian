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
        keys: ['owner-team-email', 'tech-team-email']
    actions:
      - type: tag
        key: "owner-team-email"
        value: "12345_123_com"
      - type: tag
        key: "tech-team-email"
        value: "23456_123_com"