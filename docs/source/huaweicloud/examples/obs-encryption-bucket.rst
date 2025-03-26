OBS - Configuration Encryption For Unencrypted Buckets
========================

.. code-block:: yaml

  policies:
    - name: encryption-bucket
      resource: huaweicloud.obs
      filters:
        - type: bucket-not-encrypted
          state: absent
      actions:
        - type: set-bucket-encryption
          encryption:
            method: SSE-KMS
            kms_key_id: a62cf912-898c-4f6g-a911-197cjd4a6f48