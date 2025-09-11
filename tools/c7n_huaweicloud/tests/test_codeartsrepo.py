from huaweicloud_common import BaseTest


class CodeArtsRepoTest(BaseTest):

    def test_project_query(self):
        factory = self.replay_flight_data("codeartsrepo_project_query")
        p = self.load_policy(
            {"name": "list_projects_v4", "resource": "huaweicloud.codeartsrepo-project"},
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_open_watermark(self):
        factory = self.replay_flight_data("codeartsrepo_open_watermark")
        p = self.load_policy(
            {
                "name": "codeartsrepo_open_watermark",
                "resource": "huaweicloud.codeartsrepo-project",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "a8833a48b02540a2becc254f35b1f21e",
                    }
                ],
                "actions": [{"type": "open-watermark"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(resources[0]["project_id"], "a8833a48b02540a2becc254f35b1f21e")

    def test_create_protected_branches_for_project(self):
        factory = self.replay_flight_data("codeartsrepo_create_protected_branches")
        p = self.load_policy(
            {
                "name": "codeartsrepo_create_protected_branches",
                "resource": "huaweicloud.codeartsrepo-project",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "a8833a48b02540a2becc254f35b1f21e",
                    }
                ],
                "actions": [
                    {
                        "type": "create-protected-branches",
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(resources[0]["project_id"], "a8833a48b02540a2becc254f35b1f21e")

    def test_set_project_inherit_settings(self):
        factory = self.replay_flight_data("codeartsrepo_set_project_inherit_settings")
        p = self.load_policy(
            {
                "name": "codeartsrepo_set_project_inherit_settings",
                "resource": "huaweicloud.codeartsrepo-project",
                "filters": [
                    {
                        "type": "value",
                        "key": "id",
                        "value": "a8833a48b02540a2becc254f35b1f21e",
                    }
                ],
                "actions": [
                    {
                        "type": "set-project-inherit-settings",
                        "protected_branches_enable": True,
                        "watermark_enable": True
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(resources[0]["project_id"], "a8833a48b02540a2becc254f35b1f21e")
