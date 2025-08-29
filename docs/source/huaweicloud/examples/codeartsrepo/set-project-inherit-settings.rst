CodeArtsRepo - set project inherit settings for project
========================

.. code-block:: yaml

  policies:
    - name: CodeArtsRepo-Project-Set-Project-Inherit-Settings
      description: set project inherit settings for project
      resource: huaweicloud.codeartsrepo-project
      filters:
        - type: value
          key: id
          value: "a8833a48b02540a2becc254f35b1f21e"
      actions:
        - type: set-project-inherit-settings
          protected_branches_enable: True
          watermark_enable: True


.. code-block:: yaml

  policies:
    - name: CodeArtsRepo-Project-Set-Project-Inherit-Settings
      description: set project inherit settings for project
      resource: huaweicloud.codeartsrepo-project
      filters:
        - type: value
          key: id
          op: not-equal
          value: ""
      actions:
        - type: set-project-inherit-settings
          protected_branches_enable: True
          watermark_enable: True


.. code-block:: yaml

  policies:
    - name: CodeArtsRepo-Project-Set-Project-Inherit-Settings
      description: set project inherit settings for project
      resource: huaweicloud.codeartsrepo-project
      filters:
        - type: value
          key: id
          op: in
          value: ["$project_id1", "${project_id2}"]
      actions:
        - type: set-project-inherit-settings
          protected_branches_enable: True
          watermark_enable: True