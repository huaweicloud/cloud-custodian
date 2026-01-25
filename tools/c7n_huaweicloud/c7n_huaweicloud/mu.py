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
import random
import re

from c7n.mu import get_exec_options, custodian_archive as base_archive
from c7n.utils import local_session
from c7n.exceptions import PolicyExecutionError
from c7n_huaweicloud.utils.json_parse import safe_json_parse

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
    BatchDeleteFunctionTriggersRequest,
    ShowFunctionAsyncInvokeConfigRequest,
    UpdateFunctionAsyncInvokeConfigRequest,
    UpdateFunctionAsyncInvokeConfigRequestBody,
    FuncAsyncDestinationConfig,
    FuncDestinationConfig,
    DeleteFunctionAsyncInvokeConfigRequest,
    ListFunctionTagsRequest,
    DeleteTagsRequest,
    UpdateFunctionTagsRequestBody,
    KvItem,
    CreateTagsRequest,
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
from huaweicloudsdkvpc.v2 import ListSubnetsRequest
from huaweicloudsdkvpc.v3 import ListVpcsRequest
from huaweicloudsdklts.v2 import ListLogGroupsRequest, ListLogStreamsRequest

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
            request = ListFunctionsRequest(
                marker=str(market),
                maxitems=str(maxitems),
                func_name=prefix,
            )
            try:
                response = self.client.list_functions(request)
            except exceptions.ClientRequestException as e:
                log.error(f'List functions failed, '
                          f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                          f'request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                raise PolicyExecutionError(f'List functions failed, '
                                           f'account:[{self.session.domain_name}/'
                                           f'{self.session.domain_id}], '
                                           f'request id:[{e.request_id}], '
                                           f'status code:[{e.status_code}], '
                                           f'error code:[{e.error_code}], '
                                           f'error message:[{e.error_msg}].')
            count = response.count
            next_marker = response.next_marker
            functions += safe_json_parse(response.functions)
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
        # 配置标签
        if params.get('func_tags'):
            tags = json.dumps(params.get('func_tags'))
            log.info(f'Create function with tags: {tags}')
            request_body.tags = tags
        request.body = request_body
        try:
            response = self.client.create_function(request)
        except exceptions.ClientRequestException as e:
            log.error(f'Create function failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'Create function failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

        return response

    def get_custodian_depend_version_id(self, runtime="Python3.10"):
        depend_name = f'custodian-huaweicloud-{runtime}'
        list_dependencies_request = ListDependenciesRequest(runtime=runtime, name=depend_name)
        try:
            dependencies = self.client.list_dependencies(list_dependencies_request).dependencies
        except exceptions.ClientRequestException as e:
            log.error(f'List dependencies failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'List dependencies failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

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
                log.error(f'Show dependency version failed, '
                          f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                          f'request id:[{e.request_id}], '
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

        if len(dependency_versions) == 0:
            raise PolicyExecutionError(f'Not find any dependency named: {depend_name}')

        log.info(
            f'Can not find public dependency, using private dependency {dependency_versions}')
        return dependency_versions

    def show_function_config(self, func_name, is_public=False):
        request = ShowFunctionConfigRequest(function_urn=func_name)
        try:
            response = self.client.show_function_config(request)
        except exceptions.ClientRequestException as e:
            if is_public and e.status_code == 404:
                log.warning(f'Can not find function[{func_name}], will create.')
                return None
            else:
                log.error(f'Show function config failed, '
                          f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                          f'request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'Show function config failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

        return response

    def update_function_config(self, old_config, need_update):
        old_config = old_config.to_dict()
        allow_parameters_list = [
            "timeout", "handler", "memory_size", "gpu_memory", "gpu_type", "user_data",
            "encrypted_user_data", "xrole", "app_xrole", "description", "func_vpc", "peering_cidr",
            "mount_config", "strategy_config", "custom_image", "extend_config",
            "initializer_handler", "initializer_timeout", "pre_stop_handler", "pre_stop_timeout",
            "ephemeral_storage", "enterprise_project_id", "log_config", "network_controller",
            "is_stateful_function", "enable_dynamic_memory", "enable_auth_in_header",
            "domain_names", "restore_hook_handler", "restore_hook_timeout", "heartbeat_handler",
            "enable_class_isolation", "enable_lts_log", "lts_custom_tag",
            "user_data_encrypt_kms_key_id",
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
            log.error(f'Update function config failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'Update function config failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

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
            depend_version_list=self.get_custodian_depend_version_id(func.runtime),
            code_encrypt_kms_key_id=func.code_encrypt_kms_key_id,
        )
        try:
            response = self.client.update_function_code(request)
        except exceptions.ClientRequestException as e:
            log.error(f'Update function code failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'Update function code failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

        return response

    def list_function_triggers(self, func_urn):
        request = ListFunctionTriggersRequest(function_urn=func_urn)
        try:
            response = self.client.list_function_triggers(request)
        except exceptions.ClientRequestException as e:
            log.error(f'List function triggers failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'List function triggers failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

        return response.body

    def publish(self, func, role=None):
        try:
            result = self._create_or_update(func, role)
        except PolicyExecutionError:
            raise
        func.func_urn = result.func_urn

        try:
            self._publish_triggers(func, role)
        except PolicyExecutionError:
            raise

        results = []
        if result:
            results.append(result)
        return results

    def _create_or_update(self, func, role=None):
        role = func.xrole or role
        if not role:
            raise PolicyExecutionError("FunctionGraph function xrole must be specified")
        archive = func.get_archive()
        existing = self.show_function_config(func.func_name, is_public=True)

        if existing:
            result = old_config = existing
            if self.calculate_sha512(archive) != old_config.digest:
                log.info(f'Updating function[{func.func_name}] code...')
                result = self.update_function_code(func, archive)
            need_update = self.compare_function_config(old_config, func)
            if need_update:
                log.info(f'Updating function[{func.func_name}] config: [{need_update}]...')
                result = self.update_function_config(old_config, need_update)
            if func.func_tags:
                self.process_function_tags(func.func_tags, result.func_urn)
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

        if result:
            self.process_async_invoke_config(func, result.func_urn)
        else:
            raise PolicyExecutionError("Create or update failed.")

        return result

    def _publish_triggers(self, func, role=None):
        for e in func.get_events(self.session_factory):
            changed = e.compare(func.func_urn)
            if changed is None:
                pass
            elif changed is True:
                delete_triggers = e.remove(func.func_urn)
                if delete_triggers:
                    log.info("Batch delete function triggers success.")
            else:
                continue
            create_trigger = e.add(func.func_urn)
            if create_trigger:
                log.info(
                    f'Created trigger(s) for function[{func.func_name}].')  # noqa: E501

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
            # 跳过异步配置、环境变量、vpc配置、网络控制配置、func_tags、日志配置
            if param in ["async_invoke_config", "user_data", "func_vpc", "network_controller",
                         "func_tags", "log_config"]:
                continue
            if params[param] != old_config.get(param):
                need_update_params[param] = params[param]

        # 单独比较user_data:
        if new_user_data != old_user_data:
            need_update_params['user_data'] = json.dumps(new_user_data)
        # 单独比较func_vpc:
        if not old_config['func_vpc']:
            if params['func_vpc']:
                # 开启vpc
                need_update_params['func_vpc'] = params['func_vpc']
            else:
                pass
        else:
            if params['func_vpc']:
                vpc_fields = ['vpc_id', 'subnet_id', 'is_safety']
                for field in vpc_fields:
                    if old_config['func_vpc'][field] != params['func_vpc'][field]:
                        need_update_params['func_vpc'] = params['func_vpc']
            else:
                # 关闭vpc
                need_update_params['func_vpc'] = params['func_vpc']
        # 单独比较network_controller:
        if (old_config['network_controller'] is None) or (params['network_controller'] is None):
            need_update_params['network_controller'] = params['network_controller']
        else:
            if old_config['network_controller']['disable_public_network'] != \
                    params['network_controller']['disable_public_network']:
                need_update_params['network_controller'] = params['network_controller']
        # 单独比较日志配置:
        if params['log_config']:
            if old_config.get('log_group_id') == params['log_config']['group_id'] and \
                    old_config.get('log_stream_id') == params['log_config']['stream_id']:
                pass
            else:
                need_update_params['log_config'] = params['log_config']

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
                log.error(f'Show function async config failed, '
                          f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                          f'request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                raise PolicyExecutionError(f'Show function async config failed, '
                                           f'account:[{self.session.domain_name}/'
                                           f'{self.session.domain_id}], '
                                           f'request id:[{e.request_id}], '
                                           f'status code:[{e.status_code}], '
                                           f'error code:[{e.error_code}], '
                                           f'error message:[{e.error_msg}].')

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
                log.error(f'Update function async config failed, '
                          f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                          f'request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                raise PolicyExecutionError(f'Update function async config failed, '
                                           f'account:[{self.session.domain_name}/'
                                           f'{self.session.domain_id}], '
                                           f'request id:[{e.request_id}], '
                                           f'status code:[{e.status_code}], '
                                           f'error code:[{e.error_code}], '
                                           f'error message:[{e.error_msg}].')
        elif old_config and not new_config:
            delete_async_config_request = DeleteFunctionAsyncInvokeConfigRequest(
                function_urn=func_urn
            )
            try:
                log.info('Delete function async config')
                _ = self.client.delete_function_async_invoke_config(delete_async_config_request)
            except exceptions.ClientRequestException as e:
                log.error(f'Delete function async config failed, '
                          f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                          f'request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                raise PolicyExecutionError(f'Delete function async config failed, '
                                           f'account:[{self.session.domain_name}/'
                                           f'{self.session.domain_id}], '
                                           f'request id:[{e.request_id}], '
                                           f'status code:[{e.status_code}], '
                                           f'error code:[{e.error_code}], '
                                           f'error message:[{e.error_msg}].')

    def process_function_tags(self, func_tags, func_urn):
        new_tags = func_tags
        new_tags_map = {}
        for tag in new_tags:
            new_tags_map[tag['key']] = tag['value']
        list_function_tags_request = ListFunctionTagsRequest(
            resource_type='functions',
            resource_id=func_urn
        )
        try:
            old_tags = self.client.list_function_tags(list_function_tags_request).tags
        except exceptions.ClientRequestException as e:
            log.error(f'List function tags failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'List function tags failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')
        need_delete_tags = []
        if old_tags is None or len(old_tags) == 0:
            pass
        else:
            for tag in old_tags:
                if tag.key in new_tags_map.keys() and tag.value == new_tags_map[tag.key]:
                    # tag已存在时跳过
                    pass
                else:
                    need_delete_tags.append(tag)

        if need_delete_tags:
            delete_tags_request = DeleteTagsRequest(
                resource_type='functions',
                resource_id=func_urn,
            )
            delete_tags_request.body = UpdateFunctionTagsRequestBody(
                action='delete',
                tags=need_delete_tags,
            )
            try:
                log.warning(f'Delete function tags{need_delete_tags}...')
                _ = self.client.delete_tags(delete_tags_request)
            except exceptions.ClientRequestException as e:
                log.error(f'Delete function tags failed, '
                          f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                          f'request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                raise PolicyExecutionError(f'Delete function tags failed, '
                                           f'account:[{self.session.domain_name}/'
                                           f'{self.session.domain_id}], '
                                           f'request id:[{e.request_id}], '
                                           f'status code:[{e.status_code}], '
                                           f'error code:[{e.error_code}], '
                                           f'error message:[{e.error_msg}].')

        create_tags = []
        for key, value in new_tags_map.items():
            create_tags.append(KvItem(
                key=key,
                value=value
            ))

        if create_tags == old_tags:
            # tags无需更新
            return

        create_tags_request = CreateTagsRequest(
            resource_type='functions',
            resource_id=func_urn,
        )
        create_tags_request.body = UpdateFunctionTagsRequestBody(
            action='create',
            tags=create_tags,
        )
        try:
            log.warning(f'Create function tags{create_tags}...')
            _ = self.client.create_tags(create_tags_request)
        except exceptions.ClientRequestException as e:
            log.error(f'Create function tags failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'Create function tags failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

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

    def remove(self, func):
        func_urn = func.func_urn
        if not func_urn:
            log.error('No func_urn for delete function.')
            return
        request = DeleteFunctionRequest(function_urn=func_urn)
        try:
            log.warning(f'Removing function[{func_urn}]...')
            _ = self.client.delete_function(request)
        except exceptions.ClientRequestException as e:
            log.error(f'Delete function failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'Delete function failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

        log.info(f'Remove function[{func_urn}] success.')

        return


class AbstractFunctionGraph:
    """Abstract base class for lambda functions."""
    __metaclass__ = abc.ABCMeta

    @property
    @abc.abstractmethod
    def func_urn(self):
        """Urn for the FunctionGraph function"""

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

    @property
    @abc.abstractmethod
    def user_data_encrypt_kms_key_id(self):
        """KMS key id for encrypt user data"""

    @property
    @abc.abstractmethod
    def code_encrypt_kms_key_id(self):
        """KMS key id for encrypt function code"""

    @property
    @abc.abstractmethod
    def func_tags(self):
        """Function tags"""

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
            'user_data_encrypt_kms_key_id': self.user_data_encrypt_kms_key_id,
            'code_encrypt_kms_key_id': self.code_encrypt_kms_key_id,
            'func_tags': self.func_tags,
        }
        if conf["func_vpc"]:
            conf["network_controller"] = {
                "disable_public_network": True,
            }
        else:
            conf["network_controller"] = {
                "disable_public_network": False,
            }

        return conf


class FunctionGraph(AbstractFunctionGraph):

    def __init__(self, func_data, archive):
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
    def func_urn(self):
        return self.func_data['func_urn']

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

    @property
    def user_data_encrypt_kms_key_id(self):
        return self.func_data.get('user_data_encrypt_kms_key_id', "")

    @property
    def code_encrypt_kms_key_id(self):
        return self.func_data.get('code_encrypt_kms_key_id', "")

    @property
    def func_tags(self):
        return self.func_data.get('func_tags', None)

    def get_events(self, session_factory):
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
        self.session = self.policy.session_factory()
        self.archive = custodian_archive(packages=self.packages)
        self._func_urn = None

    @property
    def func_urn(self):
        return self._func_urn

    @func_urn.setter
    def func_urn(self, urn):
        self._func_urn = urn

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
        is_safety_support_region = ["sa-brazil-1"]
        func_vpc = self.policy.data['mode'].get('func_vpc')
        if func_vpc:
            if func_vpc.get('vpc_id') and func_vpc.get('subnet_id'):
                pass
            else:
                vpc_id, subnet_id = self.get_vpc_and_subnet_id_by_name(
                    vpc_name=func_vpc["vpc_name"],
                    subnet_name=func_vpc["subnet_name"],
                    cidr=func_vpc["cidr"],
                )
                func_vpc["vpc_id"] = vpc_id
                func_vpc["subnet_id"] = subnet_id
            # 设置安全访问默认值，函数服务部分只支持部分局点开启安全访问
            if not func_vpc.get('is_safety'):
                func_vpc["is_safety"] = self.session.region in is_safety_support_region

        return func_vpc

    @property
    def user_data(self):
        user_data = {
            "HUAWEI_DEFAULT_REGION": self.session.region,
            "LOG_LEVEL": self.policy.data['mode'].get('log_level', "WARNING"),
        }
        if self.session.domain_id:
            user_data["DOMAIN_ID"] = self.session.domain_id
        if self.session.domain_name:
            user_data["DOMAIN_NAME"] = self.session.domain_name
        return json.dumps(user_data)

    @property
    def description(self):
        return self.policy.data['mode'].get('description', 'cloud-custodian FunctionGraph policy')

    @property
    def enable_lts_log(self):
        return self.policy.data['mode'].get('enable_lts_log', False)

    @property
    def log_config(self):
        log_config = self.policy.data['mode'].get('log_config', None)
        if log_config:
            if log_config.get('group_id') and log_config.get('stream_id'):
                return log_config
            log_config["group_id"], log_config["stream_id"] = \
                self.get_group_and_stream_id_by_name(
                    group_name=log_config.get('group_name', ""),
                    stream_name=log_config.get('stream_name', ""),
                )

        return log_config

    def eg_agency(self):
        return self.policy.data['mode'].get('eg_agency')

    @property
    def packages(self):
        return self.policy.data['mode'].get('packages')

    @property
    def async_invoke_config(self):
        return self.policy.data['mode'].get('async_invoke_config', None)

    @property
    def user_data_encrypt_kms_key_id(self):
        return self.policy.data['mode'].get('user_data_encrypt_kms_key_id', None)

    @property
    def code_encrypt_kms_key_id(self):
        return self.policy.data['mode'].get('code_encrypt_kms_key_id', None)

    @property
    def func_tags(self):
        return self.policy.data['mode'].get('func_tags', None)

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

    def get_vpc_and_subnet_id_by_name(self, vpc_name, subnet_name, cidr):
        vpc_client_v3 = self.session.client('vpc')
        get_vpcs_request = ListVpcsRequest(
            name=[vpc_name],
        )
        try:
            vpcs = vpc_client_v3.list_vpcs(get_vpcs_request).vpcs
        except exceptions.ClientRequestException as e:
            log.error(f'Get vpc_id by vpc_name failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError("Get vpc_id by vpc_name failed")

        vpc_id = ""
        for vpc in vpcs:
            vpc_id = vpc.id
        if not vpc_id:
            raise PolicyExecutionError(f'Get vpc_id by vpc_name[{vpc_name}] failed')

        vpc_client_v2 = self.session.client('vpc_v2')
        get_subnets_request = ListSubnetsRequest(
            vpc_id=vpc_id,
        )
        try:
            subnets = vpc_client_v2.list_subnets(get_subnets_request).subnets
        except exceptions.ClientRequestException as e:
            log.error(f'Get subnet_id by subnet_name failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError("Get subnet_id by subnet_name failed")

        subnet_id = ""
        for subnet in subnets:
            if subnet.name == subnet_name and subnet.cidr == cidr:
                subnet_id = subnet.id
                break
        if not subnet_id:
            raise PolicyExecutionError(f'Get subnet_id by subnet_name[{subnet_name}] failed')

        return vpc_id, subnet_id

    def get_group_and_stream_id_by_name(self, group_name, stream_name):
        lts_client_v2 = self.session.client('lts-stream')
        list_groups_request = ListLogGroupsRequest()
        try:
            log_groups = lts_client_v2.list_log_groups(list_groups_request).log_groups
        except exceptions.ClientRequestException as e:
            log.error(f'Get group_id by group_name failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError("Get group_id by group_name failed")
        group_id = ""
        for log_group in log_groups:
            if log_group.log_group_name == group_name or \
                    log_group.log_group_name_alias == group_name:
                group_id = log_group.log_group_id
                break
        if not group_id:
            raise PolicyExecutionError(f'Get group_id by group_name[{group_name}] failed')

        list_streams_request = ListLogStreamsRequest(
            log_group_name=group_name,
            log_stream_name=stream_name,
        )
        try:
            log_streams = lts_client_v2.list_log_streams(list_streams_request).log_streams
        except exceptions.ClientRequestException as e:
            log.error(f'Get stream_id by stream_name failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError("Get stream_id by stream_name failed")
        stream_id = ""
        for log_stream in log_streams:
            stream_id = log_stream.log_stream_id
        if not stream_id:
            raise PolicyExecutionError(f'Get stream_id by stream_name[{stream_name}] failed')

        return group_id, stream_id

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

    def compare(self, func_urn):
        raise NotImplementedError("subclass responsibility")

    def remove(self, func_urn):
        request = BatchDeleteFunctionTriggersRequest(function_urn=func_urn)
        try:
            _ = self.client.batch_delete_function_triggers(request)
        except exceptions.ClientRequestException as e:
            log.error(f'Batch delete function triggers failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'Batch delete function triggers failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

        return True


class CloudTraceServiceSource(FunctionGraphTriggerBase):

    @property
    def trigger_type_code(self):
        return "CTS"

    def add(self, func_urn):
        # Create FunctionGraph CTS trigger.
        request_body_list = self._build_request_body_list()
        for request_body in request_body_list:
            create_trigger_request = CreateFunctionTriggerRequest(function_urn=func_urn)
            create_trigger_request.body = request_body

            try:
                create_trigger_response = self.client.create_function_trigger(create_trigger_request)  # noqa: E501
                log.info(f'Create CTS trigger for function[{func_urn}] success, '
                         f'trigger id: [{create_trigger_response.trigger_id}, '
                         f'trigger name: [{create_trigger_response.event_data.name}], '
                         f'trigger status: [{create_trigger_response.trigger_status}].')
            except exceptions.ClientRequestException as e:
                log.error(f'Create function trigger failed, '
                          f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                          f'request id:[{e.request_id}], '
                          f'status code:[{e.status_code}], '
                          f'error code:[{e.error_code}], '
                          f'error message:[{e.error_msg}].')
                raise PolicyExecutionError(f'Create function trigger failed, '
                                           f'account:[{self.session.domain_name}/'
                                           f'{self.session.domain_id}], '
                                           f'request id:[{e.request_id}], '
                                           f'status code:[{e.status_code}], '
                                           f'error code:[{e.error_code}], '
                                           f'error message:[{e.error_msg}].')
        return True

    def _build_request_body_list(self):
        source_map = self._get_source_map_from_event()
        request_body_list = []
        self.trigger_names = {}

        for source, operation_list in source_map.items():
            request_body = self._build_create_cts_trigger_request_body(source, operation_list)
            if request_body:
                request_body_list.append(request_body)

        return request_body_list

    def _get_source_map_from_event(self):
        source_map = {}
        for e in self.data.get('events', []):
            source = e.get('source')
            if not source:
                continue
            if source not in source_map.keys():
                source_map[source] = []
            event = e.get("event")
            if event:
                source_map[source].append(event)

        return source_map

    def _build_create_cts_trigger_request_body(self, source, operation_list):
        request_body = CreateFunctionTriggerRequestBody(
            trigger_type_code=self.trigger_type_code,
            trigger_status="ACTIVE",
        )

        operations = []

        if source:
            service_type = source.split('.')[0]
            resource_type = source.split('.')[1]
        else:
            return

        operation = f'{service_type}:{resource_type}:{";".join(operation_list)}'
        operations.append(operation)
        default_trigger_name = self._get_default_cts_trigger_name(
            service_type,
            resource_type,
        )
        if default_trigger_name in self.trigger_names.keys():
            tmp = default_trigger_name
            if len(default_trigger_name) <= 62:
                default_trigger_name = tmp + \
                                       f'_{self.trigger_names[tmp] + 1}'
            else:
                default_trigger_name = tmp[:62] + \
                                       f'_{self.trigger_names[tmp] + 1}'
            self.trigger_names[tmp] += 1
        else:
            self.trigger_names[default_trigger_name] = 0

        request_body.event_data = {
            "name": self.data.get('trigger_name', default_trigger_name),
            "operations": operations,
        }

        return request_body

    def _get_default_cts_trigger_name(self, service_type, resource_type):
        """
        获取默认CTS触发器参数。
        命名格式:
        CTS_'service_type'_'resource_type'_'time_now'
        限制条件:
        1. 只包含字母数字及下划线
        2. 长度不超过64个字符
        """
        service_str = self._convert_special_chars(
            f'{service_type}_{resource_type}'
        )

        # 最大长度为64字符, 默认必带字符串"CTS_..._20251110154000"为19字符
        # 服务名称最长为45字符, 超出限制截断
        if len(service_str) > 45:
            service_str = service_str[:45]

        return f'CTS_{service_str}_{datetime.now().strftime("%Y%m%d%H%M%S")}'

    @staticmethod
    def _convert_special_chars(text):
        import re
        # 将非字母数字字符替换为下划线
        return re.sub(r'[^a-zA-Z0-9]', '_', text)

    def compare(self, func_urn):
        list_function_triggers_request = ListFunctionTriggersRequest(function_urn=func_urn)
        try:
            triggers = self.client.list_function_triggers(
                list_function_triggers_request).body
        except exceptions.ClientRequestException as e:
            log.error(f'List function triggers failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'List function triggers failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')
        if not triggers:
            return None
        source_map_from_triggers = {}
        for trigger in triggers:
            if trigger.trigger_type_code != self.trigger_type_code:
                continue
            operations = trigger.to_dict().get("event_data", {}).get("operations", [])
            for operation in operations:
                service_type = operation.split(':')[0]
                resource_type = operation.split(':')[1]
                action_list = operation.split(':')[2].split(';')
                source = f'{service_type}.{resource_type}'
                source_map_from_triggers[source] = action_list
        source_map_from_event = self._get_source_map_from_event()

        return source_map_from_event != source_map_from_triggers


class TimerServiceSource(FunctionGraphTriggerBase):

    @property
    def trigger_type_code(self):
        return "TIMER"

    def add(self, func_urn):
        # Create FunctionGraph TIMER trigger.
        create_trigger_request = CreateFunctionTriggerRequest(function_urn=func_urn)
        create_trigger_request.body = self._build_create_timer_trigger_request_body()

        try:
            create_trigger_response = self.client.create_function_trigger(create_trigger_request)  # noqa: E501
            log.info(f'Create TIMER trigger for function[{func_urn}] success, '
                     f'trigger id: [{create_trigger_response.trigger_id}, '
                     f'trigger name: [{create_trigger_response.event_data.name}], '
                     f'trigger status: [{create_trigger_response.trigger_status}].')
        except exceptions.ClientRequestException as e:
            log.error(f'Create function trigger failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'Create function trigger failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

        return True

    def _build_create_timer_trigger_request_body(self):
        request_body = CreateFunctionTriggerRequestBody(
            trigger_type_code=self.trigger_type_code,
            trigger_status=self.data.get('status', 'ACTIVE'),
        )
        schedule = self.data.get('schedule')
        random_offset_time = self.data.get('random_offset_time', [])
        if random_offset_time:
            log.info(f'Original cron schedule in policy: {schedule}.')
            schedule = self._get_new_schedule_by_random_offset(schedule, random_offset_time)
            log.info(f'New cron schedule by random offset: {schedule}.')
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

    def _get_new_schedule_by_random_offset(self, schedule, random_offset_time):
        offset_min, offset_max = 0, 0
        if isinstance(random_offset_time, list):
            offset_min = random_offset_time[0]
            offset_max = random_offset_time[1]
        elif isinstance(random_offset_time, str):
            offset_max = int(random_offset_time)
        elif isinstance(random_offset_time, int):
            offset_max = random_offset_time

        # 生成随机延迟秒数
        random_delay = random.randint(offset_min, offset_max)
        log.info(f'Cron schedule will delay {random_delay}s, '
                 f'in range [{offset_min}, {offset_max}].')
        # 如果延迟为0，直接返回原cron表达式
        if random_delay == 0:
            return schedule

        # 解析cron表达式
        fields = schedule.strip().split()

        if len(fields) not in [6, 7]:
            raise ValueError("cron表达式必须是6或7个字段")

        second_field = fields[0]
        minute_field = fields[1]
        hour_field = fields[2]

        delay_seconds = random_delay % 60
        delay_minutes = (random_delay // 60) % 60
        delay_hours = random_delay // 3600

        def add_to_field(field, value, max_value):
            """向cron字段添加值，处理列表和范围"""
            if field.isdigit():
                new_value = (int(field) + value) % (max_value + 1)
                return str(new_value)

            if field == '*':
                if value % (max_value + 1) == 0:
                    return '*'
                return str(value % (max_value + 1))

            step_match = re.match(r'\*/(\d+)', field)
            if step_match:
                step = int(step_match.group(1))
                if value % step == 0:
                    return field
                return str(value % (max_value + 1))

            if ',' in field:
                parts = field.split(',')
                try:
                    nums = [int(p) for p in parts]
                    new_nums = [(num + value) % (max_value + 1) for num in nums]
                    return ','.join(str(n) for n in sorted(set(new_nums)))
                except ValueError:
                    return field

            range_match = re.match(r'(\d+)-(\d+)', field)
            if range_match:
                start = int(range_match.group(1))
                end = int(range_match.group(2))
                new_start = (start + value) % (max_value + 1)
                new_end = (end + value) % (max_value + 1)
                if new_start <= new_end:
                    return f"{new_start}-{new_end}"
                else:
                    return f"{new_start}-{max_value},{0}-{new_end}"

            return field

        new_second = add_to_field(second_field, delay_seconds, 59)

        minute_carry = 0
        if second_field.isdigit():
            old_second = int(second_field)
            if old_second + delay_seconds > 59:
                minute_carry = 1
        elif second_field == '*':
            if delay_seconds > 0:
                minute_carry = 1
        else:
            minute_carry = (delay_seconds // 60)

        total_minute_add = delay_minutes + minute_carry
        new_minute = add_to_field(minute_field, total_minute_add % 60, 59)

        hour_carry = 0
        if minute_field.isdigit():
            old_minute = int(minute_field)
            if old_minute + total_minute_add > 59:
                hour_carry = 1
        elif minute_field == '*':
            if total_minute_add >= 60:
                hour_carry = 1
        else:
            hour_carry = total_minute_add // 60

        total_hour_add = delay_hours + hour_carry
        new_hour = add_to_field(hour_field, total_hour_add % 24, 23)

        new_fields = fields.copy()
        new_fields[0] = new_second
        new_fields[1] = new_minute
        new_fields[2] = new_hour

        return ' '.join(new_fields)

    def compare(self, func_urn):
        changed = True
        list_function_triggers_request = ListFunctionTriggersRequest(function_urn=func_urn)
        try:
            triggers = self.client.list_function_triggers(
                list_function_triggers_request).body
        except exceptions.ClientRequestException as e:
            log.error(f'List function triggers failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'List function triggers failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')
        if not triggers:
            return None

        schedule_type_in_policy = self.data.get('schedule_type')
        schedule_in_policy = self.data.get('schedule')
        random_offset_time = self.data.get('random_offset_time', [])
        if random_offset_time:
            return True
        if self.data.get('schedule_type') == "Cron" \
                and self.data.get('cron_tz', "") \
                and not schedule_in_policy.startswith("@every"):
            schedule_in_policy = f'CRON_TZ={self.data.get("cron_tz")} {schedule_in_policy}'

        for trigger in triggers:
            if trigger.trigger_type_code != self.trigger_type_code:
                continue
            event_data = trigger.to_dict().get("event_data", {})
            schedule_in_trigger = event_data.get("schedule", "")
            schedule_type_in_trigger = event_data.get("schedule_type", "")
            if schedule_in_trigger == schedule_in_policy and \
                    schedule_type_in_trigger == schedule_type_in_policy:
                changed = False

        return changed


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
            log.error(f'List channels failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'List channels failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')
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
            log.error(f'Create subscription failed, '
                      f'account:[{self.session.domain_name}/{self.session.domain_id}], '
                      f'request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            raise PolicyExecutionError(f'Create subscription failed, '
                                       f'account:[{self.session.domain_name}/'
                                       f'{self.session.domain_id}], '
                                       f'request id:[{e.request_id}], '
                                       f'status code:[{e.status_code}], '
                                       f'error code:[{e.error_code}], '
                                       f'error message:[{e.error_msg}].')

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

    def compare(self):
        pass
