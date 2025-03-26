SFSTurbo - Delete Unencrypted
========================

.. code-block:: yaml

  policies:
     - name: sfsturbo-last-backup-created
       description: |
         Filter the sfsturbo whose most recent backup time exceeds the parameter requirement, and bind a specific backup strategy to it.
       resource: huaweicloud.sfsturbo
       filters:
         - type: last-backup-exceed-safe-time-interval
           interval: 1
       actions:
         - type: associate-sfsturbo-vault-to-policy
           policy_id: "6f0df9bc-1aae-420c-a3e5-e272e44a3992"
