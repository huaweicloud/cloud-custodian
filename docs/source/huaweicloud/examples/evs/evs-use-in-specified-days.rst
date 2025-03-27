EVS - Delete Unencrypted
========================

.. code-block:: yaml

  policies:
     - name: evs-use-in-specified-days
       description: |
         filter evs disk which created the specified number of days age, whether is not mounted to a cloud server
       resource: huaweicloud.evs-volume
       filters:
         - and:
           - not:
             - type: value
               key: status
               value: in-use
           - type: volume-age
             days: 1
             op: gte
