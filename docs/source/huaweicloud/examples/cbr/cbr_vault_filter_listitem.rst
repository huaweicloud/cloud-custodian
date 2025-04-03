policies:
    - name: cbr_vault_filter_listitem
      resource: huaweicloud.cbr-vault
      filters:
        - type: list-item
          key: resources
          attrs:
            - type: value
              key: type
              value: "OS::Cinder::Volume"
            - type: value
              key: name
              value: "ecs-zs-custodian"
