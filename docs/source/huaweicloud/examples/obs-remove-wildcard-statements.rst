OBS - Remove Wildcrad statements in Bucket Policy
========================

.. code-block:: yaml

  policies:
    - name: remove-wildcard-statements
      resource: huaweicloud.obs
      filters:
        - type: wildcard-statements
      actions:
        - type: delete-wildcard-statements