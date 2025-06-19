policies:
  - name: cbr_vault_action_check_worm_schedule
    resource: huaweicloud.cbr-vault
    mode:
      type: huaweicloud-periodic
      xrole: fgs_admin
      eg_agency: EG_TARGET_AGENCY
      enable_lts_log: true
      schedule: "1h"
      schedule_type: Rate
    filters:
      - type: vault_without_worm
    actions:
      - type: enable_vault_worm
