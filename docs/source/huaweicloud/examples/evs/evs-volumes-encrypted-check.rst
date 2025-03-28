EVS - check unencrypted attached volumes and convert to encrypted volume
========================

.. code-block:: yaml

  policies:
  - name: volumes-encrypted-check
    description: |
         filter unencrypted attached volumes, and transform to new encrypted volume, notice old unencrypted volume wil be deleted.
    resource: huaweicloud.evs-volume
    filters:
      - or:
        - type: value
          key: metadata.__system__encrypted
          value: "0"
        - type: value
          key: metadata.__system__encrypted
          value: "empty"
      - and:
        - type: value
          key: status
          value: in-use
    actions:
      - type: encrypt-instance-data-volumes
        key: kmsKeyId