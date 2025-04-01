CES - Update CES Alarm all start.
========================

.. code-block:: yaml

    policies:
      - name: alarm-action-enabled-check
        description: "Verify that all alarm rules must be enabled and enable the disabled alarms."
        resource: huaweicloud.ces-alarm
        filters:
          - type: value
            key: enabled
            value: false
        actions:
          - type: batch-start-stopped-alarm-rules
            parameters:
              subject: "CES alarm not activated Check email"
              message: "You have the following alarms that have not been started, please check the system. The tasks have been started, please log in to the system and check again."
              notification_list:
                - "urn:smn:cn-north-4:xxxxx:CES_notification_xxxxxxx"

