CES - Check if the specified resource type is not bound to the specified indicator CES alarm
========================

.. code-block:: yaml

    policies:
      - name: alarm-resource-check
        description: "Check if the specified resource type is not bound to the specified indicator CES alarm"
        resource: huaweicloud.ces-alarm
        filters:
            - type: missing
              policy:
                resource: huaweicloud.ces-alarm
                filters:
                  - type: alarm-namespace-metric
                    namespaces: ["SYS.KMS"]
                    metric_names: ["retireGrant", "disableKey"]
                    count: [1, 2, 3, 4, 5, 10, 15, 30, 60, 90, 120, 180]
                    period: [0, 1, 300, 1200, 3600, 14400, 86400]
                    comparison_operator: ['>', '>=', '=', '!=', '<', '<=', 'cycle_decrease', 'cycle_increase', 'cycle_wave']
        actions:
          - type: notify-by-smn
            parameters:
              subject: "CES alarm not configured specified resource"
              message: "Currently, the Huawei Cloud CES system has not configured execution resource alarms. Please log in to the system to view the configuration."
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"
