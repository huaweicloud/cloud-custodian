CES - Check CES isn't configured OBS change alarm rule.
========================

.. code-block:: yaml

    policies:
      - name: alarm-obs-bucket-policy-change
        description: "Check whether the alarm for the OBS bucket policy change event is configured. If not, create a corresponding alarm."
        resource: huaweicloud.ces-alarm
        filters:
            - type: missing
              policy:
                resource: huaweicloud.ces-alarm
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
                    value: "SYS.OBS"
                    op: eq
                  - type: list-item
                    key: resources
                    attrs:
                      - type: value
                        key: "dimensions"
                        value: []
                        op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'setBucketPolicy')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'setBucketAcl')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'deleteBucketPolicy')"
                    value: true
                    op: eq
                  - type: value
                    key: "contains(policies[].metric_name, 'deleteBucket')"
                    value: true
                    op: eq
        actions:
          - type: create-obs-event-alarm-rule
            parameters:
              action_type: "notification"
              notification_list:
                - "urn:smn:cn-north-4:e196f2790965422f80502748f4d58649:CES_notification_group_kNrnzmm0J"
