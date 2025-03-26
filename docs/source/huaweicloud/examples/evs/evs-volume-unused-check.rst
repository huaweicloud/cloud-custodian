EVS - Delete Unencrypted
========================

.. code-block:: yaml

  policies:
     - name: volume-unused-check
       description: |
         filter evs disk not mounted to a cloud server
       resource: huaweicloud.evs-volume
       filters:
         - not:
           - type: value
             key: status
             value: in-use


