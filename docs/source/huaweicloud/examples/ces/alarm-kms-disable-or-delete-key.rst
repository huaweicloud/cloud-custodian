CES - Check CES isn't configured KMS change alarm rule.
========================

.. code-block:: yaml

    policies:
      - name: alarm-kms-disable-or-delete-key
        description: "Check whether the monitoring alarm for events that monitor KMS disabling or scheduled key deletion is configured. If not, create the corresponding alarm."
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
                    value: "SYS.KMS"
                    op: eq
                  - type: list-item
                    key: resources
                    attrs:
                      - type: value
                        key: "dimensions"
                        value: []
                        op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'retireGrant')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'revokeGrant')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'disableKey')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'scheduleKeyDeletion')"
                    value: true
                    op: eq
        actions:
          - type: create-kms-event-alarm-rule
            parameters:
              action_type: "notification"
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"
          - type: notify-by-smn
            parameters:
              subject: "CES alarm not configured KMS event alarm"
              message: "The system detected that you have not configured KMS event monitoring alarms, and has automatically created one for you. Please log in to the system to view it."
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"
