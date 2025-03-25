# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import abc
import hashlib
from datetime import datetime
import json
import logging
import base64

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
    DeleteFunctionRequest
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
        request_body.depend_version_list = ["8b9db9aa-274f-4aa3-b95b-0f6cf2a1bca8"]
        log.info(request_body.user_data)
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

    def show_function_config(self, func_name):
        request = ShowFunctionConfigRequest(function_urn=func_name)
        try:
            response = self.client.show_function_config(request)
        except exceptions.ClientRequestException as e:
            log.error(f'Show function config failed, request id:[{e.request_id}], '
                      f'status code:[{e.status_code}], '
                      f'error code:[{e.error_code}], '
                      f'error message:[{e.error_msg}].')
            return None

        return response

    def update_function_code(self, func_name, archive):
        request = UpdateFunctionCodeRequest(function_urn=func_name)
        base64_str = base64.b64encode(archive.get_bytes()).decode('utf-8')
        request.body = UpdateFunctionCodeRequestBody(
            code_type='zip',
            code_filename='custodian-code.zip',
            func_code=FuncCode(
                file=base64_str
            ),
            depend_version_list=["8b9db9aa-274f-4aa3-b95b-0f6cf2a1bca8"]
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
        result, _, _ = self._create_or_update(func, role)
        func.func_urn = result.func_urn
        eg_not_exist = True
        triggers = self.list_function_triggers(func.func_urn)
        if triggers is not None:
            for trigger in triggers:
                if trigger.trigger_type_code == "EVENTGRID" and trigger.trigger_status == "ACTIVE":
                    eg_not_exist = False
                    break
        if eg_not_exist:
            for e in func.get_events(self.session_factory):
                create_trigger = e.add(func.func_urn)
                if create_trigger:
                    log.info(f'Created trigger[{create_trigger.id}] for function[{func.func_name}].')  # noqa: E501
        else:
            log.info("Trigger existed, skip create.")

        return result

    def _create_or_update(self, func, role=None):
        role = func.xrole or role
        assert role, "FunctionGraph function xrole must be specified"
        archive = func.get_archive()
        existing = self.show_function_config(func.func_name)

        changed = False
        if existing:
            result = old_config = existing
            if self.calculate_sha512(archive) != old_config.digest:
                log.info(f'Updating function[{func.func_name}] code...')
                result = self.update_function_code(func.func_name, archive)
                if result:
                    changed = True
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

        return result, changed, existing

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

    def get_events(self, ssession_factory):
        return self.func_data.get('events', ())

    def get_archive(self):
        return self.archive


FunctionGraphHandlerTemplate = """\
from c7n_huaweicloud import handler

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
            "HUAWEI_DEFAULT_REGION": self.policy.data['mode'].get('default_region', "")
        }
        return json.dumps(user_data)

    @property
    def description(self):
        return self.policy.data['mode'].get('description', 'cloud-custodian FunctionGraph policy')

    def eg_agency(self):
        return self.policy.data['mode'].get('eg_agency')

    @property
    def packages(self):
        return self.policy.data['mode'].get('packages')

    def get_events(self, session_factory):
        events = []
        if self.policy.data['mode']['type'] == 'cloudtrace':
            events.append(
                CloudTraceServiceSource(
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


class CloudTraceServiceSource:
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
        create_subscription_request.body = self.build_create_subscription_request_body(channel_id, func_urn)  # noqa: E501
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
