DEH - Update Auto Placement
========================

.. code-block:: yaml

  policies:
     - name: deh-update-auto-placement
       description: |
         Update Auto Placement
       resource: huaweicloud.deh
       filters:
         - type: value
           key: name
           value: "test"
       actions:
         - type: update-dedicated-host
           dedicated_host:
             auto_placement: "off"