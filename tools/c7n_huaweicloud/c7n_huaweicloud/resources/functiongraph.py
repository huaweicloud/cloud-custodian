# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import json
from datetime import datetime, timedelta
import logging

from c7n.resolver import ValuesFrom
from c7n.utils import type_schema, parse_date, local_session
from c7n.filters import ValueFilter, OPERATORS

from huaweicloudsdkfunctiongraph.v2 import (
    ShowFunctionConfigRequest,
    ListReservedInstanceConfigsRequest,
    ListFunctionTriggersRequest,
    DeleteFunctionRequest,
    UpdateFunctionConfigRequest,
    UpdateFunctionConfigRequestBody,
    UpdateFunctionMaxInstanceConfigRequest,
    UpdateFunctionMaxInstanceConfigRequestBody,
    ListFunctionVersionsRequest,
    ListVersionAliasesRequest,
    AsyncInvokeFunctionRequest,
    InvokeFunctionRequest
)
from huaweicloudsdkcore.exceptions import exceptions
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo

log = logging.getLogger("custodian.huaweicloud.resources.functiongraph")


@resources.register('functiongraph')
class FunctionGraph(QueryResourceManager):
    class resource_type(TypeInfo):
        service = 'functiongraph'
        enum_spec = ("list_functions", 'functions', 'maxitems-marker')
        id = 'func_urn'
        tag_resource_type = 'functions'

    def get_resources(self, resource_ids):
        result = []
        for resource_id in resource_ids:
            request = ShowFunctionConfigRequest(function_urn=resource_id)
            try:
                response = self.get_client().show_function_config(request)
            except exceptions.ClientRequestException as e:
                log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                          f'error_code[{e.error_code}], '
                          f'error_msg[{e.error_msg}]')
                return result

            func_config = eval(str(response).
                               replace('null', 'None').
                               replace('false', 'False').
                               replace('true', 'True'))
            if "id" not in func_config:
                func_config["id"] = func_config["func_urn"]
            if "tag_resource_type" not in func_config:
                func_config["tag_resource_type"] = "functions"

            result.append(func_config)

        return result


@FunctionGraph.filter_registry.register('reserved-concurrency')
class ReservedConcurrency(ValueFilter):
    """Filter FunctionGraph Functions By Reserved Concurrency Config.

        :Example:

        .. code-block:: yaml

            policies:
              - name: filter-function-by-reserved-concurrency
                resource: huaweicloud.functiongraph
                filters:
                  - type: reserved-concurrency
                    key: min_count # Number of reserved instances
                    value: 1
                    key: qualifier_type # Limiting type. Options:

        """

    annotation_key = "c7n:FunctionReservedConcurrency"
    filter_key_prefix = '"c7n:FunctionReservedConcurrency".'
    schema = type_schema('reserved-concurrency',
                         rinherit=ValueFilter.schema,
                         **{'min_count': {'type': 'number'},
                            'qualifier_type': {'type': 'string', 'enum': ['version', 'alias']},
                            'qualifier_name': {'type': 'string'},
                            'idle_mode': {'type': 'boolean'},
                            }
                         )
    schema_alias = False

    def process(self, resources, event=None):
        self.data['key'] = self.filter_key_prefix + self.data['key']
        client = local_session(self.manager.session_factory).client('functiongraph')

        def _augment(r):
            request = ListReservedInstanceConfigsRequest(function_urn=r['func_urn'])
            try:
                response = client.list_reserved_instance_configs(request)
                reserved_instances = response.reserved_instances
                if reserved_instances is None:
                    return r
                for reserved_instance in reserved_instances:
                    if reserved_instance.function_urn == f'{r["func_urn"]}:{r["version"]}':
                        # change result to Python dict
                        r[self.annotation_key] = eval(
                            str(reserved_instance).
                            replace('null', 'None').
                            replace('false', 'False').
                            replace('true', 'True'))
            except exceptions.ClientRequestException as e:
                log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                          f'error_code[{e.error_code}], '
                          f'error_msg[{e.error_msg}]')
            return r

        with self.executor_factory(max_workers=3) as w:
            resources = list(filter(None, w.map(_augment, resources)))
        return super(ReservedConcurrency, self).process(resources, event)


@FunctionGraph.filter_registry.register('trigger-type')
class FunctionTrigger(ValueFilter):
    """Filter FunctionGraph Functions By Reserved Concurrency Config.

        :Example:

        .. code-block:: yaml

            policies:
              - name: filter-function-by-reserved-concurrency
                resource: huaweicloud.functiongraph
                filters:
                  - type: reserved-concurrency
                    key: min_count # Number of reserved instances
                    value: 1
                    key: qualifier_type # Limiting type. Options:

        """

    annotation_key = "c7n:FunctionTrigger"
    filter_key_prefix = '"c7n:FunctionTrigger".'
    schema = type_schema('trigger-type',
                         rinherit=ValueFilter.schema,
                         **{'trigger_id': {'type': 'string'},
                            'trigger_type_code': {'type': 'string',
                                                  'enum': ['TIMER', 'APIG', 'APIC', 'CTS', 'DDS',
                                                           'DIS', 'LTS', 'KAFAKA', 'OBS', 'SMN',
                                                           'OPENSOURCEKAFKA', 'RABBITMQ', 'IoTDA']},
                            'trigger_status': {'type': 'string', 'enum': ['ACTIVE', 'DISABLED']},
                            }
                         )
    schema_alias = False

    def process(self, resources, event=None):
        client = local_session(self.manager.session_factory).client('functiongraph')

        def _augment(r):
            request = ListFunctionTriggersRequest(function_urn=r['func_urn'])
            try:
                response = client.list_function_triggers(request)
                triggers = response.body
                if triggers is None:
                    return r
                # change result to Python dict
                r[self.annotation_key] = eval(str(triggers).
                                              replace('null', 'None').
                                              replace('false', 'False').
                                              replace('true', 'True'))
            except exceptions.ClientRequestException as e:
                log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                          f'error_code[{e.error_code}], '
                          f'error_msg[{e.error_msg}]')
            return r

        with self.executor_factory(max_workers=3) as w:
            resources = list(filter(None, w.map(_augment, resources)))
        return super(FunctionTrigger, self).process(resources, event)

    def match(self, i):
        if self.v is None and len(self.data) == 1:
            [(self.k, self.v)] = self.data.items()
        elif self.v is None and not hasattr(self, 'content_initialized'):
            self.k = self.data.get('key')
            self.op = self.data.get('op')
            if 'value_from' in self.data:
                values = ValuesFrom(self.data['value_from'], self.manager)
                self.v = values.get_values()
            elif 'value_path' in self.data:
                self.v = self.get_path_value(i)
            else:
                self.v = self.data.get('value')
            self.content_initialized = True
            self.vtype = self.data.get('value_type')

        if i is None:
            return False

        # value extract
        # Function triggers in FunctionGraph is list
        resources_triggers = i.get(self.annotation_key)

        # skip value type conversion
        v = self.v

        for trigger in resources_triggers:
            r = trigger.get(self.k)
            # Value match
            if r is None and v == 'absent':
                return True
            elif r is not None and v == 'present':
                return True
            elif v == 'not-null' and r:
                return True
            elif v == 'empty' and not r:
                return True
            elif self.op:
                op = OPERATORS[self.op]
                try:
                    return op(r, v)
                except TypeError:
                    return False
            elif r == v:
                return True

        return False


@FunctionGraph.action_registry.register("delete-function")
class DeleteFunction(HuaweiCloudBaseAction):
    """Delete FunctionGraph Functions.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-function-by-func_name
            resource: huaweicloud.functiongraph
            filters:
              - type: value
                key: func_name
                value: "test_custodian"
            actions:
              - delete-function
    """

    schema = type_schema("delete-function")

    def perform_action(self, resource):
        client = self.manager.get_client()
        func_urn = resource["func_urn"]
        if resource["version"] == 'latest':
            func_urn = ":".join(func_urn.split(":")[:-1])
        request = DeleteFunctionRequest(function_urn=func_urn)
        try:
            _ = client.delete_function(request)
            log.info(f'Function[{resource["func_name"]}] delete success.')
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return


@FunctionGraph.action_registry.register("show-function-config")
class ShowFunctionConfig(HuaweiCloudBaseAction):
    """Show FunctionGraph Function Config.

    :Example:

    . code-block:: yaml

        policies:
          - name: show-function-by-func_name
            resource: huaweicloud.functiongraph
            filters:
              - type: value
                key: func_name
                value: "test_custodian"
            actions:
              - show-function-config
    """

    schema = type_schema("show-function-config")

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = ShowFunctionConfigRequest(function_urn=resource["func_urn"])
        try:
            response = client.show_function_config(request)
            log.info(f'Function[{resource["func_name"]}] configs: {response}.')
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return


@FunctionGraph.action_registry.register("update-function-config")
class UpdateFunctionConfig(HuaweiCloudBaseAction):
    """Update FunctionGraph Function Config.

    :Example:

    . code-block:: yaml

        policies:
          - name: filter-function-by_func_name
            resource: huaweicloud.functiongraph
            filters:
              - type: value
                key: func_name
                value: test_custodian
            actions:
              - type: update-function-config
                properties: {
                  timeout: 50,
                  handler: "index.handler",
                  memory_size: 128
                }
    """

    schema = type_schema(
        "update-function-config",
        properties={'type': 'object', 'required': ["timeout", "handler", "memory_size"]}
    )

    allow_parameters_list = ["timeout", "handler", "memory_size", "gpu_memory", "gpu_type",
                             "user_data", "encrypted_user_data", "xrole", "app_xrole",
                             "description", "func_vpc", "peering_cidr", "mount_config",
                             "strategy_config", "custom_image", "extend_config",
                             "initializer_handler", "initializer_timeout", "pre_stop_handler",
                             "pre_stop_timeout", "ephemeral_storage", "enterprise_project_id",
                             "log_config", "network_controller", "is_stateful_function",
                             "enable_dynamic_memory", "enable_auth_in_header", "domain_names",
                             "restore_hook_handler", "restore_hook_timeout", "heartbeat_handler",
                             "enable_class_isolation", "lts_custom_tag"]

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = UpdateFunctionConfigRequest(function_urn=resource["func_urn"])
        request.body = self.get_request_body(resource, client)
        if request.body is None:
            log.error("Build request body failed.")
            return
        try:
            response = client.update_function_config(request)
            log.info(f'Function[{resource["func_name"]}] update success, configs: {response}.')
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return

    def get_request_body(self, resource, client):
        params = self.data.get('properties', {})
        # FunctionGraph do not support incremental update,
        # we should get the function configuration first.
        show_function_config_request = ShowFunctionConfigRequest(function_urn=resource["func_urn"])
        try:
            response = client.show_function_config(show_function_config_request)
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return None

        request_body = UpdateFunctionConfigRequestBody(
            func_name=resource['func_name'],
            runtime=resource['runtime'],
        )
        # Put the original configuration into the request body,
        # and check whether parameter is valid.
        for key, value in json.loads(response.to_str()).items():
            if key in self.allow_parameters_list:
                setattr(request_body, key, value)
        # Put user's parameter into the request body.
        for key, value in params.items():
            setattr(request_body, key, value)

        return request_body


@FunctionGraph.action_registry.register("modify-security-groups")
class ModifySecurityGroups(UpdateFunctionConfig):
    """Modify FunctionGraph Function Vpc Security Group.

    :Example:

    . code-block:: yaml

        policies:
          - name: filter-function-by_func_name
            resource: huaweicloud.functiongraph
            filters:
              - type: value
                key: func_name
                value: test_custodian
            actions:
              - type: modify-security-groups
                properties: {
                  timeout: 50,
                  handler: "index.handler",
                  memory_size: 128
                }
    """

    schema = type_schema(
        "modify-security-groups",
        xrole={"type": "string"},
        security_groups={"type": "array", "items": {"type": "string"}},
        required=('xrole', 'security_groups',),
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        show_function_config_request = ShowFunctionConfigRequest(function_urn=resource["func_urn"])
        try:
            response = client.show_function_config(show_function_config_request)
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return None
        # Check whether the function has VPC configuration,
        # only vpc function can change security groups.
        if response.func_vpc is None:
            log.error(f'Function[{resource["func_name"]}] has not vpc config, '
                      f'modify security groups failed.')
            return

        func_vpc = json.loads(str(response.func_vpc))
        func_vpc['security_groups'] = self.data.get("security_groups")
        # Build update function config properties.
        self.data["properties"] = {
            "timeout": resource["timeout"],
            "handler": resource["handler"],
            "memory_size": resource["memory_size"],
            "func_vpc": func_vpc,
            "xrole": self.data.get("xrole"),
        }

        return super(ModifySecurityGroups, self).perform_action(resource)


@FunctionGraph.action_registry.register("update-function-concurrency")
class UpdateFunctionMaxInstanceConfig(HuaweiCloudBaseAction):
    """Update FunctionGraph Function Concurrency Config.

    :Example:

    . code-block:: yaml

        policies:
          - name: update-function-concurrency-by-func_name
            resource: huaweicloud.functiongraph
            filters:
              - type: value
                key: func_name
                value: "test_custodian"
            actions:
              - type: update-function-concurrency
                value: 200
    """

    schema = type_schema(
        'update-function-concurrency',
        required=('value',),
        **{'value': {'type': 'integer'}}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        request = UpdateFunctionMaxInstanceConfigRequest(function_urn=resource["func_urn"])
        request.body = UpdateFunctionMaxInstanceConfigRequestBody(
            max_instance_num=self.data.get('value')
        )
        try:
            response = client.update_function_max_instance_config(request)
            log.info(f'Function[{resource["func_name"]}] update concurrency success, '
                     f'configs: {response}.')
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return


@FunctionGraph.action_registry.register("trim-versions")
class TrimVersions(HuaweiCloudBaseAction):
    """Delete FunctionGraph Functions.

    :Example:

    .. code-block:: yaml

        policies:
          - name: delete-function-version-by-func_name
            resource: huaweicloud.functiongraph
            filters:
              - type: value
                key: func_name
                value: "test_custodian"
            actions:
              - trim-versions
                exclude-aliases: true
                older-than: 1
    """

    schema = type_schema(
        'trim-versions',
        **{'exclude-aliases': {'default': True, 'type': 'boolean'},
           'retain-latest': {'default': True, 'type': 'boolean'},
           'older-than': {'type': 'number'}})

    def perform_action(self, resource):
        client = self.manager.get_client()
        request_for_versions = ListFunctionVersionsRequest(function_urn=resource["func_urn"])
        try:
            versions = client.list_function_versions(request_for_versions).versions
        except exceptions.ClientRequestException as e:
            log.error(f'List function[{resource["func_name"]}] versions failed.')
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return
        request_for_aliases = ListVersionAliasesRequest(function_urn=resource["func_urn"])
        try:
            aliases = client.list_version_aliases(request_for_aliases).body
        except exceptions.ClientRequestException as e:
            log.error(f'List function[{resource["func_name"]}] aliases failed.')
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return
        if len(versions) == 1 and versions[0].version == "latest":
            log.warning(f'{resource["func_name"]} only have [latest] version, '
                        f'cannot trim versions.')
            return
        versions_binding_aliases = {}
        if aliases is not None:
            for alias_config in aliases:
                versions_binding_aliases[alias_config.version] = alias_config
        version_names_list = []
        for version in versions:
            if self.skip_delete_function_version(version, versions_binding_aliases):
                continue
            self.delete_version(client, version.func_urn)
            version_names_list.append(f'{resource["func_name"]}.{version.version}')
        log.info(f'Deleted versions: {version_names_list}')

    @staticmethod
    def delete_version(client, func_urn):
        request = DeleteFunctionRequest(function_urn=func_urn)
        try:
            log.warning(f'Deleting {func_urn}')
            _ = client.delete_function(request)
            log.info(f'{func_urn} deleted.')
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return

    def skip_delete_function_version(self, version, versions_binding_aliases):
        if version.version == 'latest':
            log.info("version[latest] cannot delete, skip delete.")
            return True
        exclude_aliases = self.data.get("exclude-aliases", True)
        if exclude_aliases and (version.version in versions_binding_aliases.keys()):
            log.info(f'version[{version.version}] is bound by '
                     f'alias[{versions_binding_aliases[version.version].name}], skip delete.')
            return True

        date_threshold = self.data.get('older-than')
        date_threshold = (
                date_threshold and
                parse_date(datetime.now()) - timedelta(days=date_threshold) or
                None
        )
        # TODO: need to calculate timezone
        if date_threshold:
            return parse_date(version.last_modified) > date_threshold
        return False


@FunctionGraph.action_registry.register("invoke-function")
class InvokeFunction(HuaweiCloudBaseAction):
    """Update FunctionGraph Function Concurrency Config.

    :Example:

    . code-block:: yaml

        policies:
          - name: update-function-concurrency-by-func_name
            resource: huaweicloud.functiongraph
            filters:
              - type: value
                key: func_name
                value: "test_custodian"
            actions:
              - type: invoke-function
                body: {
                  "k": "v"
                }
                async-invoke: true
    """

    schema = type_schema(
        'invoke-function',
        required=('body',),
        body={'type': 'object'},
        **{'X-Cff-Log-Type': {'type': 'string', 'default': None, 'enum': ['tail', None]},
           'X-Cff-Request-Version': {'type': 'string', 'default': 'v1', 'enum': ['v1', 'v2']},
           'async-invoke': {'type': 'boolean', 'default': False}
           }
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        if self.data.get("X-Cff-Request-Version") is None:
            self.data["X-Cff-Request-Version"] = "v1"
        if self.data.get('async-invoke'):
            request = AsyncInvokeFunctionRequest(function_urn=resource["func_urn"])
        else:
            request = InvokeFunctionRequest(function_urn=resource["func_urn"],
                                            x_cff_log_type=self.data.get('X-Cff-Log-Type'),
                                            x_cff_request_version=self.data.get('X-Cff-Request-Version'))
        request.body = self.data.get('body')
        if self.data.get('async-invoke'):
            try:
                response = client.async_invoke_function(request)
                log.info(f'Function[{resource["func_name"]}] async invoke success, '
                         f'request id[{response.request_id}]')
            except exceptions.ClientRequestException as e:
                log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                          f'error_code[{e.error_code}], '
                          f'error_msg[{e.error_msg}]')
                return
        else:
            try:
                response = client.invoke_function(request)
                if self.data.get("X-Cff-Request-Version") == "v1":
                    log.info(f'Function[{resource["func_name"]}] invoke success, '
                             f'request id[{response.request_id}], '
                             f'result: [{response.result}], '
                             f'log: [{response.log}]')
                else:
                    log.info(f'Function[{resource["func_name"]}] invoke success, '
                             f'request id[{response.x_cff_request_id}]')
            except exceptions.ClientRequestException as e:
                log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                          f'error_code[{e.error_code}], '
                          f'error_msg[{e.error_msg}]')
                return
