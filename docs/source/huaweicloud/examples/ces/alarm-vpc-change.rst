CES - Check CES isn't configured VPC change alarm rule.
========================

.. code-block:: yaml

    policies:
      - name: alarm-vpc-change
        description: "Check whether the event monitoring alarm for monitoring VPC changes is configured. If not, create the corresponding alarm."
        resource: huaweicloud.alarm
        filters:
            - type: missing
              policy:
                resource: huaweicloud.alarm
                filters:
                  - type: value
                    key: enabled
                    value: true
                    op: eq
                  - type: value
                    key: type
                    value: "EVENT.SYS"
                    op: eq
                  - type: value
                    key: namespace
                    value: "SYS.VPC"
                    op: eq
                  - type: list-item
                    key: resources
                    attrs:
                      - type: value
                        key: "dimensions"
                        value: []
                        op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'modifyVpc')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'modifySubnet')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'deleteSubnet')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'modifyBandwidth')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'deleteVpn')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'modifyVpc')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'modifyVpn')"
                    value: true
                    op: eq
        actions:
          - type: create-vpc-event-alarm-rule
            parameters:
              action_type: "notification"
              notification_list:
                - "urn:smn:cn-north-4:xxxxxx:CES_notification_xxxxxx"
