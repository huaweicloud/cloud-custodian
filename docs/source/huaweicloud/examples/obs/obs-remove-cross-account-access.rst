OBS - Deletes Bucket Policy Statement That Containing Bucket Blacklisted Actions
========================

.. code-block:: yaml
    policies:
      - name: remove-cross-account-access
        resource: huaweicloud.obs
        filters:
          - type: cross-account
        actions:
          - type: remove-cross-account-config