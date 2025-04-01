AntiDDoS - Enable Anti-DDoS for unprotected EIP
========================

.. code-block:: yaml

  policies:
    - name: eip-enable-antiddos
      resource: huaweicloud.antiddos-eip
      filters:
        - type: value
          key: status
          value: "notConfig"
      actions:
        - enable
