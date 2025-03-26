EVS - check last backup creation time exceed safe time interval
========================

.. code-block:: yaml

  policies:
  - name: last-backup-exceed-safe-time-interval
    resource: huaweicloud.evs-volume
    filters:
      - type: last-backup-exceed-safe-time-interval
        interval: 1
    actions:
      - type: add-volume-to-vault
        vault_id: vault_id
      - type: associate-volume-vault-to-policy
        policy_id: policy_id
      - backup
