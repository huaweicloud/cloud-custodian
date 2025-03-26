EVS - Volume Detach
========================

.. code-block:: yaml

  policies:
     - name: volume-detach
       resource: huaweicloud.evs-volume
       filters:
         - and:
           - type: value
             key: status
             value: "in-use"
           - type: value
             key: bootable
             value: "False"
       actions:
         - detach
