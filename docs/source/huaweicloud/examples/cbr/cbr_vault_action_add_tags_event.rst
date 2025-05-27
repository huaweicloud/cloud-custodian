policies:
  - name: cbr_vault_action_add_tags_event
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
        - source: "CBR.vault"
          event: "bulkCreateOrDeleteVaultTag"
          ids: "resource_id"
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