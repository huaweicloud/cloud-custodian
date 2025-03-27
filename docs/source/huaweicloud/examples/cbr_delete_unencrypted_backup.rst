policies:
    - name: delete-unencrypted-backup
      resource: huaweicloud.cbr-backup
      filters:
        - and:
          - type: value
            key: extend_info.encrypted
            value: false
          - type: value
            key: resource_type
            value: "OS::Cinder::Volume"
      actions:
          - delete
