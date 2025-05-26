OBS - Find Obs Bucket That missing Some Tags
========================

.. code-block:: yaml

  policies:
    - name: missing-bucket-tags
        resource: huaweicloud.obs
        filters:
        - type: obs-missing-tag-filter
            tags:
            - key: key1
              value: value1
            - key: key2
              value: value2
            match: missing-any

  policies:
    - name: missing-bucket-tags
        resource: huaweicloud.obs
        filters:
        - type: obs-missing-tag-filter
            tags:
            - key: key1
              value: value1
            - key: key2
              value: value2
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