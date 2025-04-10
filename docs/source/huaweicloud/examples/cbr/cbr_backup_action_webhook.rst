policies:
    - name: cbr_backup_action_webhook
      resource: huaweicloud.cbr-backup
      actions:
        - type: webhook
          url: https://console.huaweicloud.com/console/?agencyId=658345a2dbeb46e69220a04a455a4fb1&region=ap-southeast-1&locale=zh-cn#/cbr/manager/csbsBackupDetail
          query-params:
            backup_id: 'resource.id'
            backup_name: 'resource.name'
          method: GET


