policies:
  - name: cbr_protectable_server_with_vault_event
    resource: huaweicloud.cbr-protectable
    mode:
      type: cloudtrace
      xrole: fgs_admin
      eg_agency: EG_TARGET_AGENCY
      enable_lts_log: true
      events:
        - source: "ECS.ecs"
          event: "createServer"
          ids: "resource_id"
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
