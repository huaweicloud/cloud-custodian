policies:
  - name: cbr_protectable_server_with_vault_schedule
    resource: huaweicloud.cbr-protectable
    mode:
      type: huaweicloud-periodic
      xrole: fgs_admin
      eg_agency: EG_TARGET_AGENCY
      enable_lts_log: true
      schedule: "1h"
      schedule_type: Rate
    filters:
      - and:
        - not:
          - type: value
            op: contains
            key: detail.tags
            value: "backup_policy=False"
        - type: value
          key: protectable.vault
          value: empty
    actions:
      - type: associate_server_with_vault
        name: "new_vault"
