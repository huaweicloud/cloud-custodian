OBS - Find Obs Bucket That missing Some Tags
========================

.. code-block:: yaml

  policies:
    - name: missing-bucket-tags
        resource: huaweicloud.obs
        filters:
        - type: obs-missing-tag-filter
            tags:
            - key: owner-team-email
              value: ^[a-zA-Z0-9._%+-]+@gmail.com$
            - key: data_classification
              value: ^(Restricted|Internal|Public|Confidential)$
            - key: bucket-type
              value: log-bucket
            - key: team
            match: missing-any

  policies:
    - name: missing-bucket-tags
        resource: huaweicloud.obs
        filters:
        - type: obs-missing-tag-filter
            tags:
            - key: owner-team-email
              value: ^[a-zA-Z0-9._%+-]+@gmail.com$
            - key: data_classification
              value: ^(Restricted|Internal|Public|Confidential)$
            - key: bucket-type
              value: log-bucket
            - key: team
            match: missing-all

  policies:
    - name: missing-bucket-tags
        resource: huaweicloud.obs
        filters:
        - type: obs-missing-tag-filter
            tags:
            - key: key1
            - key: key2
            match: missing-all