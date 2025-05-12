# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import abc
import hashlib
from datetime import datetime
import json
import logging
import base64
import site
import zipfile
import os

from c7n.mu import get_exec_options, custodian_archive as base_archive
from c7n.utils import local_session

from huaweicloudsdkfunctiongraph.v2 import (
    ListFunctionsRequest,
    CreateFunctionRequest,
    CreateFunctionRequestBody,
    ShowFunctionConfigRequest,
    UpdateFunctionCodeRequest,
    UpdateFunctionCodeRequestBody,
    FuncCode,
    ListFunctionTriggersRequest,
    DeleteFunctionRequest,
    CreateFunctionTriggerRequest,
    CreateFunctionTriggerRequestBody,
    ListDependenciesRequest,
    ShowDependencyVersionRequest,
    UpdateFunctionConfigRequest,
    UpdateFunctionConfigRequestBody,
    DeleteFunctionTriggerRequest,
    ShowFunctionAsyncInvokeConfigRequest,
    UpdateFunctionAsyncInvokeConfigRequest,
    UpdateFunctionAsyncInvokeConfigRequestBody,
    FuncAsyncDestinationConfig,
    FuncDestinationConfig,
    DeleteFunctionAsyncInvokeConfigRequest,
)
from huaweicloudsdkeg.v1 import (
    ListChannelsRequest,
    CreateSubscriptionRequest,
    TransForm,
    SubscriptionSource,
    SubscriptionTarget,
    SubscriptionCreateReq
)
from huaweicloudsdkcore.exceptions import exceptions

log = logging.getLogger('c7n_huaweicloud.mu')


def custodian_archive(packages=None):
    if not packages:
        packages = []
    packages.append('c7n_huaweicloud')
    archive = base_archive(packages)

    return archive


def package_dependencies(zip_filename):
    log.info(f'Start package dependencies to {zip_filename}')
    site_packages_dirs = site.getsitepackages()
    zip_filepath = os.path.abspath(zip_filename)
    with zipfile.ZipFile(zip_filename, "w", zipfile.ZIP_DEFLATED) as zipf:
        for sp_dir in site_packages_dirs:
            if not os.path.exists(sp_dir):
                continue

            for root, dirs, files in os.walk(sp_dir):
                # Filter directories: skip cache and metadata directories
                dirs[:] = [
                    d for d in dirs
                    if d not in {"__pycache__"}
                       and not d.endswith(".egg-info")
                ]
                # Filter files: skip .pyc, .pth, .dll, .exe and .pdb files
                files = [
                    f for f in files
                    # Forced Lowercase Matching
                    if not f.lower().endswith((".pyc", ".pth", ".dll", ".exe", ".pdb"))
                ]

                for file in files:
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, sp_dir)
                    zipf.write(file_path, arcname=arcname)

    # 获取 ZIP 文件大小
    file_size = os.path.getsize(zip_filepath)

    # 转换为 Base64
    with open(zip_filepath, "rb") as f:
        zip_data = f.read()
    base64_data = base64.b64encode(zip_data).decode("utf-8")
    log.info(f'Package dependencies success, filepath: {zip_filepath}, zip file size: {file_size}')  # noqa: E501

    return file_size, base64_data


class FunctionGraphManager:

    def __init__(self, session_factory):
        self.session_factory = session_factory
        self.session = local_session(session_factory)
        self.client = self.session.client('functiongraph')

    def list_functions(self, prefix=None):
        market, maxitems, count = 0, 400, 0
        functions = []

        while 1:
            request = ListFunctionsRequest(marker=str(market), maxitems=str(maxitems))
            try:
                response = self.client.list_functions(request)
            except exceptions.ClientRequestException as e:
                log.error(f'List functions failed, request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                return functions
            count = response.count
            next_marker = response.next_marker
            functions += eval(str(response).
                              replace('null', 'None').
                              replace('false', 'False').
                              replace('true', 'True'))
            market = next_marker
            if next_marker >= count:
                break

        return functions

    def create_function(self, params):
        request = CreateFunctionRequest()
        request_body = CreateFunctionRequestBody()
        for key, value in params.items():
            setattr(request_body, key, value)
        # 配置公共依赖
        dep_ids = self.get_custodian_depend_version_id(params["runtime"])
        request_body.depend_version_list = dep_ids
        request.body = request_body
        try:
            response = self.client.create_function(request)
        except exceptions.ClientRequestException as e:
            log.error(f'Create function failed, request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            return None

        return response

    def get_custodian_depend_version_id(self, runtime="Python3.10") -> list[str]:
        depend_name = f'custodian-huaweicloud-{runtime}'
        list_dependencies_request = ListDependenciesRequest(runtime=runtime, name=depend_name)
        try:
            dependencies = self.client.list_dependencies(list_dependencies_request).dependencies
        except exceptions.ClientRequestException as e:
            log.error(f'List dependencies failed, request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            return []

        dependency_versions = []
        dependency_version_map = {}
        for dependency in dependencies:
            show_dependency_version_request = ShowDependencyVersionRequest(
                depend_id=dependency.id,
                version=dependency.version,
            )
            try:
                dependency_version = self.client.show_dependency_version(show_dependency_version_request)  # noqa: E501
            except exceptions.ClientRequestException as e:
                log.error(f'Show dependency version failed, request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                continue
            owner = dependency_version.owner
            dependency_version_id = dependency_version.id
            if dependency_version_map.get(owner):
                dependency_version_map.append(dependency_version_id)
            else:
                dependency_version_map[owner] = [dependency_version_id]

        for owner, dependency_version_list in dependency_version_map.items():
            if owner == "public":
                dependency_versions = dependency_version_list
                log.info(f'Using public dependency {dependency_version_list}')
                return dependency_versions
            else:
                dependency_versions += dependency_version_list
                log.info(
                    f'Can not find public dependency, using [{owner}] private dependency {dependency_version_list}')  # noqa: E501

        if len(dependency_versions) == 0:
            log.error(f'Not find any dependency named: {depend_name}, please add dependencies manually')  # noqa: E501

        return dependency_versions

    def show_function_config(self, func_name, is_public=False):
        request = ShowFunctionConfigRequest(function_urn=func_name)
        try:
            response = self.client.show_function_config(request)
        except exceptions.ClientRequestException as e:
            if is_public and e.status_code == 404:
                log.warning(f'Can not find function[{func_name}], will create.')
            else:
                log.error(f'Show function config failed, request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
            return None

        return response

    def update_function_config(self, old_config, need_update):
        old_config = old_config.to_dict()
        allow_parameters_list = [
            "timeout", "handler", "memory_size", "gpu_memory", "gpu_type", "xrole", "app_xrole",
            "description", "func_vpc", "peering_cidr", "mount_config", "strategy_config",
            "custom_image", "extend_config", "initializer_handler", "initializer_timeout",
            "pre_stop_handler", "pre_stop_timeout", "ephemeral_storage", "enterprise_project_id",
            "log_config", "network_controller", "is_stateful_function", "enable_dynamic_memory",
            "enable_auth_in_header", "domain_names", "restore_hook_handler",
            "restore_hook_timeout", "heartbeat_handler", "enable_class_isolation",
            "enable_lts_log", "lts_custom_tag"
        ]
        request = UpdateFunctionConfigRequest(function_urn=old_config["func_urn"])
        request_body = UpdateFunctionConfigRequestBody(
            func_name=old_config['func_name'],
            runtime=old_config['runtime'],
        )
        if 'enable_lts_log' not in need_update:
            old_config.pop('enable_lts_log', None)
        # Put the original configuration into the request body, and check whether parameter is valid.  # noqa: E501
        for key, value in old_config.items():
            if key in allow_parameters_list:
                setattr(request_body, key, value)
        # Put update parameter into the request body.
        for key, value in need_update.items():
            setattr(request_body, key, value)
        request.body = request_body
        try:
            response = self.client.update_function_config(request)
        except exceptions.ClientRequestException as e:
            log.error(f'Update function config failed, request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            return None

        return response

    def update_function_code(self, func, archive):
        request = UpdateFunctionCodeRequest(function_urn=func.func_name)
        base64_str = base64.b64encode(archive.get_bytes()).decode('utf-8')
        request.body = UpdateFunctionCodeRequestBody(
            code_type='zip',
            code_filename='custodian-code.zip',
            func_code=FuncCode(
                file=base64_str
            ),
            depend_version_list=self.get_custodian_depend_version_id(func.runtime)
        )
        try:
            response = self.client.update_function_code(request)
        except exceptions.ClientRequestException as e:
            log.error(f'Update function code failed, request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            return None

        return response

    def list_function_triggers(self, func_urn):
        request = ListFunctionTriggersRequest(function_urn=func_urn)
        try:
            response = self.client.list_function_triggers(request)
        except exceptions.ClientRequestException as e:
            log.error(f'List function triggers failed, request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            return []

        return response.body

    def publish(self, func, role=None):
        result, changed, _ = self._create_or_update(func, role)
        func.func_urn = result.func_urn

        if changed:
            triggers = self.list_function_triggers(func.func_urn)
            for e in func.get_events(self.session_factory):
                if triggers is not None:
                    for trigger in triggers:
                        if trigger.trigger_type_code == e.trigger_type_code:
                            update_trigger = e.remove(trigger.trigger_id, func.func_urn)
                            if update_trigger:
                                log.info(f'Delete trigger[{trigger.trigger_id}] success.')
                create_trigger = e.add(func.func_urn)
                if create_trigger:
                    log.info(
                        f'Created trigger[{create_trigger.trigger_id}] for function[{func.func_name}].')  # noqa: E501

        results = []
        if result:
            results.append(result)
        return results

    def _create_or_update(self, func, role=None):
        role = func.xrole or role
        assert role, "FunctionGraph function xrole must be specified"
        archive = func.get_archive()
        existing = self.show_function_config(func.func_name, is_public=True)

        changed = False
        if existing:
            result = old_config = existing
            if self.calculate_sha512(archive) != old_config.digest:
                log.info(f'Updating function[{func.func_name}] code...')
                result = self.update_function_code(func, archive)
                if result:
                    changed = True
            need_update = self.compare_function_config(old_config, func)
            if need_update:
                log.info(f'Updating function[{func.func_name}] config: [{need_update}]...')
                result = self.update_function_config(old_config, need_update)
        else:
            log.info(f'Creating custodian policy FunctionGraph function[{func.func_name}]...')
            params = func.get_config()
            params.update({
                'func_code': {
                    'file': base64.b64encode(archive.get_bytes()).decode('utf-8')
                },
                'code_type': 'zip',
                'code_filename': 'custodian-code.zip'
            })
            result = self.create_function(params)
            changed = True

        if result:
            self.process_async_invoke_config(func, result.func_urn)

        return result, changed, existing

    @staticmethod
    def compare_function_config(old_config, func):
        params = func.get_config()
        old_config = old_config.to_dict()
        old_user_data, new_user_data = {}, {}
        need_update_params = {}
        # 将user_data字段转为dict, 便于比较
        if params.get('user_data', ""):
            new_user_data = json.loads(params['user_data'])
        if old_config.get('user_data', ""):
            old_user_data = json.loads(old_config['user_data'])
        for param in params:
            # 跳过异步配置、环境变量
            if param in ["async_invoke_config", "user_data"]:
                continue
            if params[param] != old_config.get(param):
                need_update_params[param] = params[param]

        # 单独比较user_data:
        if new_user_data != old_user_data:
            need_update_params['user_data'] = json.dumps(new_user_data)
        return need_update_params

    def process_async_invoke_config(self, func, func_urn):
        show_async_config_request = ShowFunctionAsyncInvokeConfigRequest(
            function_urn=func_urn
        )
        try:
            old_config = self.client.show_function_async_invoke_config(
                show_async_config_request).to_dict()
        except exceptions.ClientRequestException as e:
            if int(e.status_code) == 404:
                old_config = None
            else:
                log.error(f'Show function async config failed, request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                return

        new_config = func.async_invoke_config
        if new_config:
            update_async_config_request = UpdateFunctionAsyncInvokeConfigRequest(
                function_urn=func_urn
            )
            update_async_config_request.body = UpdateFunctionAsyncInvokeConfigRequestBody(
                enable_async_status_log=new_config.get('enable_async_status_log'),
                max_async_retry_attempts=new_config.get('max_async_retry_attempts'),
                max_async_event_age_in_seconds=new_config.get('max_async_event_age_in_seconds'),
                destination_config=FuncAsyncDestinationConfig(
                    on_success=FuncDestinationConfig(
                        destination=new_config.get('destination_config', {}).
                        get('on_success', {}).
                        get('destination', ""),
                        param=json.dumps(
                            new_config.get('destination_config', {}).
                            get('on_success', {}).
                            get('param', {})),
                    ),
                    on_failure=FuncDestinationConfig(
                        destination=new_config.get('destination_config', {}).
                        get('on_failure', {}).
                        get('destination', ""),
                        param=json.dumps(
                            new_config.get('destination_config', {}).
                            get('on_failure', {}).
                            get('param', {})),
                    ),
                )
            )
            try:
                log.info('Update function async config...')
                _ = self.client.update_function_async_invoke_config(
                    update_async_config_request
                )
            except exceptions.ClientRequestException as e:
                log.error(f'Update function async config failed, request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                return
        elif old_config and not new_config:
            delete_async_config_request = DeleteFunctionAsyncInvokeConfigRequest(
                function_urn=func_urn
            )
            try:
                log.info('Delete function async config')
                _ = self.client.delete_function_async_invoke_config(delete_async_config_request)
            except exceptions.ClientRequestException as e:
                log.error(f'Delete function async config failed, request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                return

    @staticmethod
    def calculate_sha512(archive, buffer_size=65536) -> str:
        """计算文件的 SHA512 哈希值"""
        sha512 = hashlib.sha512()

        with archive.get_stream() as f:
            while True:
                data = f.read(buffer_size)
                if not data:
                    break
                sha512.update(data)

        return sha512.hexdigest()

    def remove(self, func_urn):
        request = DeleteFunctionRequest(function_urn=func_urn)
        try:
            log.warning(f'Removing function[{func_urn}]...')
            _ = self.client.delete_function(request)
        except exceptions.ClientRequestException as e:
            log.error(f'Delete function failed, request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            return

        log.info(f'Remove function[{func_urn}] success.')

        return


class AbstractFunctionGraph:
    """Abstract base class for lambda functions."""
    __metaclass__ = abc.ABCMeta

    @property
    @abc.abstractmethod
    def func_name(self):
        """Name for the FunctionGraph function"""

    @property
    @abc.abstractmethod
    def event_name(self):
        """Name for EG trigger"""

    @property
    @abc.abstractmethod
    def package(self):
        """ """

    @property
    @abc.abstractmethod
    def runtime(self):
        """ """

    @property
    @abc.abstractmethod
    def timeout(self):
        """ """

    @property
    @abc.abstractmethod
    def handler(self):
        """ """

    @property
    @abc.abstractmethod
    def memory_size(self):
        """ """

    @property
    @abc.abstractmethod
    def xrole(self):
        """IAM agency for function, this field is mandatory when a function needs to access other services."""  # noqa: E501

    @property
    @abc.abstractmethod
    def func_vpc(self):
        """VPC configuration"""

    @property
    @abc.abstractmethod
    def user_data(self):
        """ """

    @property
    @abc.abstractmethod
    def description(self):
        """ """

    @property
    @abc.abstractmethod
    def enable_lts_log(self):
        """Whether open lts log"""

    @property
    @abc.abstractmethod
    def log_config(self):
        """LTS log config"""

    @property
    @abc.abstractmethod
    def async_invoke_config(self):
        """Async invoke config"""

    @abc.abstractmethod
    def get_events(self, session_factory):
        """ """

    @abc.abstractmethod
    def get_archive(self):
        """Return func_code"""

    def get_config(self):
        conf = {
            'func_name': self.func_name,
            'package': self.package,
            'runtime': self.runtime,
            'timeout': self.timeout,
            'handler': self.handler,
            'memory_size': self.memory_size,
            'xrole': self.xrole,
            'func_vpc': self.func_vpc,
            'user_data': self.user_data,
            'description': self.description,
            'enable_lts_log': self.enable_lts_log,
            'log_config': self.log_config,
            'async_invoke_config': self.async_invoke_config,
        }

        return conf


class FunctionGraph(AbstractFunctionGraph):

    def __int__(self, func_data, archive):
        self.func_data = func_data
        required = {
            'func_name', 'package', 'runtime',
            'timeout', 'handler', 'memory_size',
            'xrole'
        }
        missing = required.difference(func_data)
        if missing:
            raise ValueError("Missing required keys %s" % " ".join(missing))
        self.archive = archive

    @property
    def func_name(self):
        return self.func_data['func_name']

    event_name = func_name

    @property
    def package(self):
        return self.func_data['package']

    @property
    def runtime(self):
        return self.func_data['runtime']

    @property
    def timeout(self):
        return self.func_data['timeout']

    @property
    def handler(self):
        return self.func_data['handler']

    @property
    def memory_size(self):
        return self.func_data['memory_size']

    @property
    def xrole(self):
        return self.func_data['xrole']

    @property
    def func_vpc(self):
        return self.func_data.get('func_vpc', None)

    @property
    def user_data(self):
        return self.func_data.get('user_data', "")

    @property
    def description(self):
        return self.func_data.get('description', "")

    @property
    def enable_lts_log(self):
        return self.func_data.get('enable_lts_log', False)

    @property
    def log_config(self):
        return self.func_data.get('log_config', None)

    @property
    def async_invoke_config(self):
        return self.func_data.get('async_invoke_config', None)

    def get_events(self, ssession_factory):
        return self.func_data.get('events', ())

    def get_archive(self):
        return self.archive


FunctionGraphHandlerTemplate = """\
from c7n_huaweicloud import handler
import logging
import os

logging.basicConfig(level=os.getenv("LOG_LEVEL"))

def run(event, context):
    return handler.run(event, context)

"""


class PolicyFunctionGraph(AbstractFunctionGraph):

    def __init__(self, policy):
        self.policy = policy
        self.archive = custodian_archive(packages=self.packages)

    @property
    def func_name(self):
        prefix = self.policy.data['mode'].get('function-prefix', 'custodian-')
        return "%s%s" % (prefix, self.policy.name)

    event_name = func_name

    @property
    def package(self):
        return self.policy.data['mode'].get('package', 'default')

    @property
    def runtime(self):
        return self.policy.data['mode'].get('runtime', 'Python3.10')

    @property
    def timeout(self):
        return self.policy.data['mode'].get('timeout', 900)

    @property
    def handler(self):
        return self.policy.data['mode'].get('handler', 'custodian_policy.run')

    @property
    def memory_size(self):
        return self.policy.data['mode'].get('memory_size', 512)

    @property
    def xrole(self):
        return self.policy.data['mode'].get('xrole', '')

    @property
    def func_vpc(self):
        return self.policy.data['mode'].get('func_vpc', None)

    @property
    def user_data(self):
        user_data = {
            "HUAWEI_DEFAULT_REGION": local_session(self.policy.session_factory).region,
            "LOG_LEVEL": self.policy.data['mode'].get('log_level', "WARNING"),
        }
        return json.dumps(user_data)

    @property
    def description(self):
        return self.policy.data['mode'].get('description', 'cloud-custodian FunctionGraph policy')

    @property
    def enable_lts_log(self):
        return self.policy.data['mode'].get('enable_lts_log', False)

    @property
    def log_config(self):
        return self.policy.data['mode'].get('log_config', None)

    def eg_agency(self):
        return self.policy.data['mode'].get('eg_agency')

    @property
    def packages(self):
        return self.policy.data['mode'].get('packages')

    @property
    def async_invoke_config(self):
        return self.policy.data['mode'].get('async_invoke_config', None)

    def get_events(self, session_factory):
        events = []
        if self.policy.data['mode']['type'] == 'cloudtrace':
            events.append(
                CloudTraceServiceSource(
                    self.policy.data['mode'], session_factory))
        elif self.policy.data['mode']['type'] == 'huaweicloud-periodic':
            events.append(
                TimerServiceSource(
                    self.policy.data['mode'], session_factory))
        return events

    def get_archive(self):
        self.archive.add_contents(
            'config.json', json.dumps(
                {'execution-options': get_exec_options(self.policy.options),
                 'policies': [self.policy.data]}, indent=2))
        self.archive.add_contents('custodian_policy.py', FunctionGraphHandlerTemplate)
        self.archive.close()
        return self.archive


class FunctionGraphTriggerBase:
    client_service = 'functiongraph'

    def __init__(self, data, session_factory):
        self.session_factory = session_factory
        self._session = None
        self._client = None
        self.data = data

    @property
    def session(self):
        if not self._session:
            self._session = self.session_factory()
        return self._session

    @property
    def client(self):
        if not self._client:
            self._client = self.session.client(self.client_service)
        return self._client

    @property
    def trigger_type_code(self):
        raise NotImplementedError("subclass responsibility")

    def add(self, func_urn):
        raise NotImplementedError("subclass responsibility")

    def remove(self, trigger_id, func_urn):
        request = DeleteFunctionTriggerRequest(function_urn=func_urn,
                                               trigger_type_code=self.trigger_type_code,
                                               trigger_id=trigger_id)
        try:
            _ = self.client.delete_function_trigger(request)
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return False

        return True


class CloudTraceServiceSource(FunctionGraphTriggerBase):

    @property
    def trigger_type_code(self):
        return "CTS"

    def add(self, func_urn):
        # Create FunctionGraph CTS trigger.
        create_trigger_request = CreateFunctionTriggerRequest(function_urn=func_urn)
        create_trigger_request.body = self.build_create_cts_trigger_request_body()

        try:
            create_trigger_response = self.client.create_function_trigger(create_trigger_request)  # noqa: E501
            log.info(f'Create CTS trigger for function[{func_urn}] success, '
                     f'trigger id: [{create_trigger_response.trigger_id}, '
                     f'trigger name: [{create_trigger_response.event_data.name}], '
                     f'trigger status: [{create_trigger_response.trigger_status}].')
            return create_trigger_response
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return False

    def build_create_cts_trigger_request_body(self):
        request_body = CreateFunctionTriggerRequestBody(
            trigger_type_code=self.trigger_type_code,
            trigger_status="ACTIVE",
        )
        operations = []
        source_map = {}
        for e in self.data.get('events', []):
            source = e.get('source')
            if source:
                service_type = source.split('.')[0]
                resource_type = source.split('.')[1]
            else:
                continue
            if service_type not in source_map.keys():
                source_map[service_type] = {
                    "resource_type_list": [],
                    "trace_name_list": []
                }
            if resource_type not in source_map[service_type]["resource_type_list"]:
                source_map[service_type]["resource_type_list"].append(resource_type)
            event = e.get("event")
            if event and (event not in source_map[service_type]["trace_name_list"]):
                source_map[service_type]["trace_name_list"].append(event)

        for service_type in source_map:
            resource_types = ";".join(source_map[service_type]["resource_type_list"])
            trace_names = ";".join(source_map[service_type]["trace_name_list"])
            operation = f'{service_type}:{resource_types}:{trace_names}'
            operations.append(operation)
        request_body.event_data = {
            "name": self.data.get('trigger_name',
                                  'custodian_timer_' + datetime.now().strftime("%Y%m%d%H%M%S")),
            "operations": operations
        }

        return request_body


class TimerServiceSource(FunctionGraphTriggerBase):

    @property
    def trigger_type_code(self):
        return "TIMER"

    def add(self, func_urn):
        # Create FunctionGraph TIMER trigger.
        create_trigger_request = CreateFunctionTriggerRequest(function_urn=func_urn)
        create_trigger_request.body = self.build_create_timer_trigger_request_body()

        try:
            create_trigger_response = self.client.create_function_trigger(create_trigger_request)  # noqa: E501
            log.info(f'Create TIMER trigger for function[{func_urn}] success, '
                     f'trigger id: [{create_trigger_response.trigger_id}, '
                     f'trigger name: [{create_trigger_response.event_data.name}], '
                     f'trigger status: [{create_trigger_response.trigger_status}].')
            return create_trigger_response
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return False

    def build_create_timer_trigger_request_body(self):
        request_body = CreateFunctionTriggerRequestBody(
            trigger_type_code=self.trigger_type_code,
            trigger_status=self.data.get('status', 'ACTIVE'),
        )
        schedule = self.data.get('schedule')
        if self.data.get('schedule_type') == "Cron" \
                and self.data.get('cron_tz', "") \
                and not schedule.startswith("@every"):
            schedule = f'CRON_TZ={self.data.get("cron_tz")} {schedule}'
        request_body.event_data = {
            "name": self.data.get('trigger_name',
                                  'custodian_timer_' + datetime.now().strftime("%Y%m%d%H%M%S")),
            "schedule_type": self.data.get('schedule_type'),
            "schedule": schedule,
        }

        return request_body


class EventGridServiceSource:
    client_service = 'eg'

    def __init__(self, data, session_factory):
        self.session_factory = session_factory
        self._session = None
        self._client = None
        self.data = data

    @property
    def session(self):
        if not self._session:
            self._session = self.session_factory()
        return self._session

    @property
    def client(self):
        if not self._client:
            self._client = self.session.client(self.client_service)
        return self._client

    def add(self, func_urn):
        # Get OFFICIAL channels
        list_channels_request = ListChannelsRequest(provider_type="OFFICIAL")
        try:
            list_channels_response = self.client.list_channels(list_channels_request)
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return False
        if list_channels_response.size == 0:
            log.error("EventGrid no OFFICIAL channels.")
            return False
        channel_id = list_channels_response.items[0].id
        # Create EG subscription, target is FunctionGraph.
        create_subscription_request = CreateSubscriptionRequest()
        create_subscription_request.body = self.build_create_subscription_request_body(channel_id,
                                                                                       func_urn)  # noqa: E501
        try:
            create_subscription_response = self.client.create_subscription(create_subscription_request)  # noqa: E501
            log.info(f'Create EG trigger for function[{func_urn}] success, '
                     f'trigger id: [{create_subscription_response.id}, '
                     f'trigger name: [{create_subscription_response.name}], '
                     f'trigger status: [{create_subscription_response.status}].')
            return create_subscription_response
        except exceptions.ClientRequestException as e:
            log.error(f'Request[{e.request_id}] failed[{e.status_code}], '
                      f'error_code[{e.error_code}], '
                      f'error_msg[{e.error_msg}]')
            return False

    def build_create_subscription_request_body(self, channel_id, func_urn):
        target_transform = TransForm(
            type="ORIGINAL",
            value=""
        )
        subscription_sources = []
        for e in self.data.get('events', []):
            subscription_sources.append(SubscriptionSource(
                name="HC." + e.get('source'),
                provider_type="OFFICIAL",
                detail={},
                filter={
                    'source': [{
                        'op': 'StringIn',
                        'values': ['HC.' + e.get('source')],
                    }],
                    'type': [{
                        'op': 'StringEndsWith',
                        'values': ['ConsoleAction', 'ApiCall']
                    }],
                    'data': {
                        'service_type': [{
                            'op': 'StringIn',
                            'values': [e.get('source')]
                        }],
                        'trace_name': [{
                            'op': 'StringIn',
                            'values': [e.get('event')]
                        }]
                    }
                }
            ))

        subscription_target = [
            SubscriptionTarget(
                name='HC.FunctionGraph',
                provider_type='OFFICIAL',
                detail={
                    'urn': func_urn,
                    'agency_name': self.data.get('eg_agency'),
                    'invoke_type': self.data.get('invoke_type', 'SYNC')
                },
                retry_times=self.data.get('retry_times', 16),
                transform=target_transform
            )
        ]

        return SubscriptionCreateReq(
            name='custodian-' + datetime.now().strftime("%Y%m%d%H%M%S"),
            channel_id=channel_id,
            sources=subscription_sources,
            targets=subscription_target
        )
