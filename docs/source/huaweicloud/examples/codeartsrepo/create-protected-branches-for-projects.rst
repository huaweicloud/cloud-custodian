CodeArtsRepo - create protected branch for project
========================

.. code-block:: yaml

  policies:
    - name: CodeArtsRepo-Project-Create-Protected-Branches
      description: create protected branch for project
      resource: huaweicloud.codeartsrepo-project
      filters:
        - type: value
          key: id
          value: "${project_id}"
      actions:
        - type: create-protected-branches


.. code-block:: yaml

  policies:
    - name: CodeArtsRepo-Project-Create-Protected-Branches
      description: create protected branch for projects
      resource: huaweicloud.codeartsrepo-project
      filters:
        - type: value
          op: not-equal
          value: ""
      actions:
        - type: create-protected-branches


.. code-block:: yaml

  policies:
    - name: CodeArtsRepo-Project-Create-Protected-Branches
      description: create protected branch for projects
      resource: huaweicloud.codeartsrepo-project
      filters:
        - type: value
          op: in
          value: ["$project_id1", "${project_id2}"]
      actions:
        - type: create-protected-branches