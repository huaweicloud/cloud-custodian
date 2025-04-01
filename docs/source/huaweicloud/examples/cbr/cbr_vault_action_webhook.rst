policies:
    - name: cbr_vault_action_webhook
      resource: huaweicloud.cbr-vault
      actions:
        - type: webhook
          url: https://console.huaweicloud.com/console/?agencyId=658345a2dbeb46e69220a04a455a4fb1&region=ap-southeast-1&locale=zh-cn#/cbr/manager/vbsVaultDetail
          query-params:
            vault_id: 'resource.id'
            vault_name: 'resource.name'
          method: GET


