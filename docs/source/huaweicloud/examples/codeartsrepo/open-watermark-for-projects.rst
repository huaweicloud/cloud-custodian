CodeArtsRepo - open watermark for project
========================

.. code-block:: yaml

  policies:
    - name: CodeArtsRepo-Project-Open-Watermark
      description: open watermark for project
      resource: huaweicloud.codeartsrepo-project
      filters:
        - type: value
          key: id
          value: "${project_id}"
      actions:
        - type: open-watermark


.. code-block:: yaml

  policies:
    - name: CodeArtsRepo-Project-Open-Watermark
      description: open watermark for projects
      resource: huaweicloud.codeartsrepo-project
      filters:
        - type: value
          key: id
          op: not-equal
          value: ""
      actions:
        - type: open-watermark


.. code-block:: yaml

  policies:
    - name: CodeArtsRepo-Project-Open-Watermark
      description: open watermark for projects
      resource: huaweicloud.codeartsrepo-project
      filters:
        - type: value
          key: id
          op: in
          value: ["$project_id1", "${project_id2}"]
      actions:
        - type: open-watermark