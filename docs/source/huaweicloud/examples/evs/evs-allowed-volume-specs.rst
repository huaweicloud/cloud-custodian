EVS - Delete Unencrypted
========================

.. code-block:: yaml

  policies:
     - name: allowed-volume-specs
       description: |
         filter evs disk not in the specified volume type list
       resource: huaweicloud.evs-volume
       filters:
         - not:
           - type: value
             key: volume_type
             op: in
             value: ["GPSSD", "SSD"]


