EVS - Volume Create Snapshot
========================

.. code-block:: yaml

  policies:
     - name: volume-create-snapshot
       resource: huaweicloud.evs-volume
       actions:
         - type: snapshot
           force: True
