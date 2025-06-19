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
        backup_policy_id: "bc715c62-f4ed-4fc0-9e78-ce43b9409a39"
        consistent_level: "crash_consistent"
        object_type: "server"
        protect_type: "backup"
        size: 100
        charging_mode: "post_paid"
        period_type: "year"
        period_num: 1
        is_auto_renew: true
        is_auto_pay: true
        name: "new_vault"