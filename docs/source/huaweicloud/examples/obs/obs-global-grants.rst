OBS - Deletes Global Grants Associated To A Obs Bucket
========================

.. code-block:: yaml
    policies:
      - name: obs-delete-global-grants
        resource: huaweicloud.obs
        filters:
          - type: global-grants
        actions:
          - type: delete-global-grants
