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
        keys: ['must-tag-key1', 'must-tag-key2']
    actions:
      - type: tag
        key: "must-tag-key1"
        value: "must-tag-value1"
      - type: tag
        key: "must-tag-key2"
        value: "must-tag-value2"