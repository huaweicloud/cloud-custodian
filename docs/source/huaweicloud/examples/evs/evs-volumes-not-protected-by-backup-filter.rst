EVS - check volume not protected by backup
========================

.. code-block:: yaml

  policies:
  - name: volume-not-protected-by-backup
    resource: huaweicloud.evs-volume
    filters:
      - not-protected-by-backup
    actions:
      - type: add-volume-to-vault
        vault_id: vault_id