CES - Update CES Alarm notification settings.
========================

.. code-block:: yaml

    policies:
      - name: ces-alarm-have-smn-check
        description: "Filter all alarm rules that do not have notifications enabled. Update the SMN notifications corresponding to these alarm settings"
        resource: huaweicloud.ces-alarm
        filters:
          - type: value
            key: notification_enabled
            value: false
        actions:
          - type: alarm-update-notification
            parameters:
              action_type: "notification"
              notification_name: "Email_Notification_to_Owner"


