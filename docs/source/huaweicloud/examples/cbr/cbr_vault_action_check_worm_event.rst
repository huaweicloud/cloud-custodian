policies:
  - name: cbr_vault_action_check_worm_event
    resource: huaweicloud.cbr-vault
    mode:
      type: cloudtrace
      xrole: fgs_admin
      eg_agency: EG_TARGET_AGENCY
      enable_lts_log: true
      events:
        - source: "CBR.vault"
          event: "createVault"
          ids: "resource_id"
    filters:
      - type: vault_without_worm
    actions:
      - type: enable_vault_worm
