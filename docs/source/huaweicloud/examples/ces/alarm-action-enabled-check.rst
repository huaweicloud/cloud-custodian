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
          - type: batch-start-alarm-rules

