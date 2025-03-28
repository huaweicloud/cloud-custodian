OBS - Configuration Encryption For Unencrypted Buckets
========================

.. code-block:: yaml

  policies:
    - name: encryption-bucket
      resource: huaweicloud.obs
      filters:
        - type: bucket-encryption
          state: False
      actions:
        - type: set-bucket-encryption
          encryption:
            crypto: kms
            key: a62cf912-898c-4f6g-a911-197cjd4a6f48