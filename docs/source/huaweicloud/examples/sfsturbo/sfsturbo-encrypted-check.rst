SFSTurbo - Delete Unencrypted
========================

.. code-block:: yaml

  policies:
     - name: sfsturbo-encrypted-check
       description: |
         filter unencrypted sfsturbo, and delete it.
       resource: huaweicloud.sfsturbo
       filters:
         - "crypt_key_id": "empty"
       actions:
         - delete
