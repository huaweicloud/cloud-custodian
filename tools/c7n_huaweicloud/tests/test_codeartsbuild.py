# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class CodeartsbuildTest(BaseTest):
    """Test class for Huawei Cloud Codeartsbuild resources"""

    # =========================
    # Resource Query Tests
    # =========================
    def test_job_query(self):
        """Test basic codeartsbuild resource query"""
        factory = self.replay_flight_data('codearts_build_job_query')
        p = self.load_policy({
            'name': 'codearts-build-job-query-test',
            'resource': 'huaweicloud.codearts-build-job'},
            session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], "0d0415bc87f647369a6b9dc9d326ba5d")

    def test_job_filter_not_exist(self):
        """Test codeartsbuild value filter for filtering by field exist."""
        factory = self.replay_flight_data("codearts_build_job_query")
        p = self.load_policy(
            {
                "name": "codearts_build_job_filter_not_exist",
                "resource": "huaweicloud.codearts-build-job",
                "filters": [{"type": "not-exist"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_job_filter_execution_host(self):
        """Test codeartsbuild value filter for filtering by field execution_host."""
        factory = self.replay_flight_data("codearts_build_job_execution_host_query")
        p = self.load_policy(
            {
                "name": "codearts_build_job_filter_not_exist",
                "resource": "huaweicloud.codearts-build-job",
                "filters": [{"type": "execution-host", "host_type": "default"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
