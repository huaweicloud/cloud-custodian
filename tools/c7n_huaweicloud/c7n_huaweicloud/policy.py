# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import time

from c7n import utils
from c7n.exceptions import PolicyValidationError
from c7n.policy import execution, ServerlessExecutionMode
from c7n.utils import type_schema
from c7n.version import version

from c7n_huaweicloud.cts import CloudTraceServiceEvents

log = logging.getLogger('c7n_huaweicloud.policy')


class FunctionGraphMode(ServerlessExecutionMode):
    schema = type_schema(
        'huaweicloud',
        access_key_id={'type': 'string'},
        secret_access_key={'type': 'string'},
        default_region={'type': 'string'},
        **{
            'execution-options': {'type': 'object'},
            'function-prefix': {'type': 'string'},
            'packages': {'type': 'array', 'items': {'type': 'string'}},
            # FunctionGraph pass through config
            'package': {'type': 'string'},
            'runtime': {'type': 'string', 'enum': ['Python3.9', 'Python3.10', 'Python3.12']},
            'timeout': {'type': 'number'},
            'handler': {'type': 'string'},
            'memory_size': {'type': 'number'},
            'xrole': {'type': 'string'},
            'func_vpc': {'type': 'object', 'required': ['vpc_id', 'subnet_id']},
            'user_data': {'type': 'string'},
            'description': {'type': 'string'},
            'eg_agency': {'type': 'string'},
            'enable_lts_log': {'type': 'boolean'},
            'log_config': {'type': 'object'},
        }
    )

    def validate(self):
        super(FunctionGraphMode, self).validate()
        prefix = self.policy.data['mode'].get('function-prefix', 'custodian-')
        MAX_FUNCTIONGRAPH_NAME_LENGTH = 64
        if len(prefix + self.policy.name) > MAX_FUNCTIONGRAPH_NAME_LENGTH:
            raise PolicyValidationError(
                "Custodian FunctionGraph policies has a max length with prefix of %s"
                " policy:%s prefix:%s" % (
                    MAX_FUNCTIONGRAPH_NAME_LENGTH,
                    self.policy.name,
                    prefix
                )
            )

    def resolve_resources(self, event):
        mode = self.policy.data.get('mode', {})
        resource_ids = CloudTraceServiceEvents.get_ids(event, mode)
        if resource_ids is None:
            raise ValueError("Unknown push event mode %s", self.data)
        log.info(f'Found resource ids:[{resource_ids}]')
        if not resource_ids:
            log.warning("Could not find resource ids")
            return []
        resources = self.policy.resource_manager.get_resources(resource_ids)
        if 'debug' in event:
            log.info("Resources %s", resources)
        return resources

    def run(self, event, context):
        if not self.policy.is_runnable(event):
            return
        resources = self.resolve_resources(event)
        if not resources:
            return resources
        rcount = len(resources)
        resources = self.policy.resource_manager.filter_resources(resources, event)

        if 'debug' in event:
            log.info("Filtered resources %d of %d", len(resources), rcount)

        if not resources:
            log.info("policy%s resources:%s no resources matched" % (
                self.policy.name, self.policy.resource_type))
            return

        return self.run_resource_set(event, resources)

    def run_resource_set(self, event, resources):
        from c7n.actions import EventAction

        with self.policy.ctx as ctx:
            ctx.metrics.put_metric(
                'ResourceCount', len(resources), 'Count', Scope="Policy", buffer=False
            )

            if 'debug' in event:
                self.policy.log.info(
                    "Invoking actions %s", self.policy.resource_manager.actions
                )

            ctx.output.write_file('resources.json', utils.dumps(resources, indent=2))

            for action in self.policy.resource_manager.actions:
                self.policy.log.info(
                    "policy:%s invoking action:%s resources:%d",
                    self.policy.name,
                    action.name,
                    len(resources),
                )
                if isinstance(action, EventAction):
                    results = action.process(resources, event)
                else:
                    results = action.process(resources)
                ctx.output.write_file("action-%s" % action.name, utils.dumps(results))
        return resources

    @property
    def policy_functiongraph(self):
        from c7n_huaweicloud import mu
        return mu.PolicyFunctionGraph

    def provision(self):
        # auto tag function policies with mode and version, we use the
        # version in mugc to effect cleanups.
        tags = self.policy.data['mode'].setdefault('tags', {})
        tags['custodian-info'] = "mode=%s:version=%s" % (
            self.policy.data['mode']['type'], version)
        # auto tag with schedule name and group to link function to
        # EventBridge schedule when using schedule mode
        if self.policy.data['mode']['type'] == 'schedule':
            prefix = self.policy.data['mode'].get('function-prefix', 'custodian-')
            name = self.policy.data['name']
            group = self.policy.data['mode'].get('group-name', 'default')
            tags['custodian-schedule'] = f'name={prefix + name}:group={group}'

        from c7n_huaweicloud import mu
        with self.policy.ctx:
            self.policy.log.info(
                "Provisioning policy FunctionGraph: %s region: %s", self.policy.name,
                self.policy.options.region)
            manager = mu.FunctionGraphManager(self.policy.session_factory)
            return manager.publish(
                self.policy_functiongraph(self.policy),
                role=self.policy.options.assume_role)

    def get_logs(self, start, end):
        pass


@execution.register('cloudtrace')
class CloudTraceMode(FunctionGraphMode):
    schema = type_schema(
        'cloudtrace',
        delay={'type': 'integer', 'description': 'sleep for delay seconds before processing an event'},  # noqa: E501
        events={'type': 'array', 'items': {
            'oneOf': [
                {'type': 'string'},
                {'type': 'object',
                 'required': ['event', 'source', 'ids'],
                 'properties': {
                     'source': {'type': 'string'},
                     'event': {'type': 'string'},
                     'ids': {'type': 'string'}
                 }}]
        }},
        rinherit=FunctionGraphMode.schema)

    def resolve_resources(self, event):
        delay = self.policy.data.get('mode', {}).get('delay')
        if delay:
            time.sleep(delay)
        return super().resolve_resources(event)
