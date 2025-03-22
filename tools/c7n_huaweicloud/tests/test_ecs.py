
from huaweicloud_common import *


class InstanceStartTest(BaseTest):

    def test_instance_query(self):
        # print(HUAWEICLOUD_CONFIG)
        factory = self.replay_flight_data('ecs_instance_query')
        p = self.load_policy({
            'name': 'list_servers_details',
            'resource': 'huaweicloud.ecs'
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 5)

    def test_instance_stop(self):
        factory = self.replay_flight_data('ecs_instance_stop')
        p = self.load_policy({
            'name': 'ecs_instance_stop',
            'resource': 'huaweicloud.ecs',
            'filters': [{"type": "value","key":"id","value":"bac642b0-a9ca-4a13-b6b9-9e41b35905b6"}],
            'actions': ["instance-stop"]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_instance_stop(self):
        factory = self.replay_flight_data('ecs_instance_start')
        p = self.load_policy({
            'name': 'ecs_instance_start',
            'resource': 'huaweicloud.ecs',
            'filters': [{"type": "value","key":"id","value":"bac642b0-a9ca-4a13-b6b9-9e41b35905b6"}],
            'actions': ["instance-start"]
        }, session_factory=factory)
        resources = p.run()
        self.assertEqual(len(resources), 1)
