policies:
  - name: cbr_vault_without_replication_policy
    resource: huaweicloud.cbr-vault
    mode:
      type: cloudtrace
      xrole: fgs
      eg_agency: EG_TARGET_AGENCY
      enable_lts_log: true
      events:
        - source: "CBR.vault"
          event: "createVault"
          ids: "resource_id"
        - source: "CBR.vault"
          event: "deleteVault"
          ids: "resource_id"
        - source: "CBR.vault"
          event: "associatePolicy"
          ids: "resource_id"
        - source: "CBR.vault"
          event: "dissociatePolicy"
          ids: "resource_id"
    filters:
      - type: unassociated_with_replication_policy