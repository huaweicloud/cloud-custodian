OBS - Action To Update Public Access Blocks On Obs Buckets
========================

.. code-block:: yaml
    policies:
        - name: CheckForPublicAclBlock-Off
          resource: huaweicloud.obs
          filters:
            - or:
              - type: check-public-block
                blockPublicAcls: false
              - type: check-public-block
                blockPublicPolicy: false
          actions:
            - type: set-public-block
              state: true


    policies:
        - name: public-block-enable-all
        resource: huaweicloud.obs
        filters:
          - type: check-public-block
        actions:
          - type: set-public-block


    policies:
        - name: public-block-enable-some
        resource: huaweicloud.obs
        filters:
          - or:
            - type: check-public-block
              blockPublicAcls: false
            - type: check-public-block
              blockPublicPolicy: false
        actions:
          - type: set-public-block
            blockPublicAcls: true
            blockPublicPolicy: true
