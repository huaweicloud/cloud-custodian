# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import json
import jmespath
from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkapig.v2 import (
    # API interface related
    DeleteApiV2Request,
    UpdateApiV2Request,
    ListApisV2Request,
    ShowDetailsOfApiV2Request,
    CreateOrDeletePublishRecordForApiV2Request,

    # Environment related
    UpdateEnvironmentV2Request,
    DeleteEnvironmentV2Request,
    ListEnvironmentsV2Request,

    # Domain related
    UpdateDomainV2Request,
    UpdateSlDomainSettingV2Request,
    SlDomainAccessSetting,

    # Group related
    ListApiGroupsV2Request,
    ShowDetailsOfApiGroupV2Request,

    # Instance related
    ListInstancesV2Request,
    ListFeaturesV2Request,
    CreateFeatureV2Request,
    FeatureToggle,

    # Plugin related
    ListPluginsRequest,
)
from huaweicloudsdklts.v2 import ListLogGroupsRequest, ListLogStreamsRequest

from c7n.exceptions import PolicyExecutionError
from c7n.filters import Filter
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.utils.json_parse import safe_json_parse

log = logging.getLogger('custodian.huaweicloud.apig')


# Instance Resource Management
@resources.register('apig-instance')
class ApigInstanceResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway Instance Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-instance'
        enum_spec = ('list_instances_v2', 'instances', 'offset')
        id = 'id'
        name = 'instance_name'
        filter_name = 'instance_name'
        filter_type = 'scalar'
        taggable = False

    def get_resources(self, resource_ids):
        resources = self.get_instance_resources()
        result = []
        for resource in resources:
            if resource["id"] in resource_ids:
                result.append(resource)
        return result

    def _fetch_resources(self, query):
        return self.get_instance_resources()

    def get_instance_resources(self):
        """Override resource retrieval method to query APIG instances"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Create new request object with pagination parameters
        request = ListInstancesV2Request(limit=500)
        # Call client method to process request
        try:
            response = client.list_instances_v2(request)
            resource = safe_json_parse(response.instances)
            return resource
        except Exception as e:
            log.error(
                "The resource:[apig-instance] query instance resources "
                "is failed, cause: %s", str(e), exc_info=True)
            raise


@ApigInstanceResource.filter_registry.register('log-analysis-unable')
class LogAnalysisUnableFilter(Filter):
    """Filter APIG instances where does not open Log Analysis

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-instance-log-analysis-unable
            resource: huaweicloud.apig-instance
            filters:
              - type: log-analysis-unable
    """

    schema = type_schema('log-analysis-unable')

    def process(self, resources, event=None):
        """
        Process resources to filter APIG instances where does not open Log Analysis

        :param resources: List of APIG instance resources
        :param event: Optional event data
        :return: Filtered list of resources matching the criteria
        """
        client = local_session(self.manager.session_factory).client("apig-instance")
        matched_resources = []

        for resource in resources:
            instance_id = resource.get('id')
            instance_name = resource.get('instance_name', 'Unknown')

            try:
                # Query instance features list
                request = ListFeaturesV2Request(instance_id=instance_id, limit=500)
                response = client.list_features_v2(request)

                # Find LTS feature in the features list
                lts_feature = None
                if response.features:
                    for feature in response.features:
                        if feature.name == 'lts':
                            lts_feature = feature
                            break

                # If LTS feature is not found, skip this instance
                if lts_feature is None:
                    log.warning(
                        "[filters]- The filter:[log-analysis-unable] "
                        "query the service:[list_features_v2] instance %s "
                        "(ID: %s) does not have LTS feature configured",
                        instance_name, instance_id)
                    continue

                # Parse config field (it's a JSON string)
                config_str = lts_feature.config
                if not config_str:
                    # If config is empty, it doesn't contain log_group
                    matched_resources.append(resource)
                    log.warning(
                        "[filters]- The filter:[log-analysis-unable] "
                        "query the service:[list_features_v2] instance %s "
                        "(ID: %s) LTS feature config is empty",
                        instance_name, instance_id)
                    continue

                try:
                    # Parse JSON config string
                    config_dict = json.loads(config_str)
                    # Check if 'log_group' key exists in the config dict
                    has_log_group = 'log_group' in config_dict
                    # Also check nested structures if container_lts_cfg is a dict
                    if not has_log_group and 'container_lts_cfg' in config_dict:
                        container_cfg = config_dict['container_lts_cfg']
                        if isinstance(container_cfg, dict) and 'log_group' in container_cfg:
                            has_log_group = True

                    if not has_log_group:
                        matched_resources.append(resource)
                        log.info(
                            "[filters]- The filter:[log-analysis-unable] "
                            "query the service:[list_features_v2] instance %s "
                            "(ID: %s) LTS feature config does not contain log_group. "
                            "Config: %s", instance_name, instance_id, config_str)
                except json.JSONDecodeError as e:
                    # If config is not valid JSON, check if it's a plain string
                    if 'log_group' not in config_str:
                        matched_resources.append(resource)
                        log.error(
                            "[filters]- The filter:[log-analysis-unable] "
                            "query the service:[list_features_v2] instance %s "
                            "(ID: %s) LTS feature config is not valid JSON and "
                            "does not contain log_group. Config: %s",
                            instance_name, instance_id, config_str)
                        raise
                    else:
                        log.error(
                            "[filters]- The filter:[log-analysis-unable] "
                            "query the service:[list_features_v2] instance %s "
                            "(ID: %s) LTS feature config is not valid JSON: %s",
                            instance_name, instance_id, e)
                        raise

            except exceptions.ClientRequestException as e:
                log.error(
                    "[filters]- The filter:[log-analysis-unable] "
                    "query the service:[list_features_v2] query features for APIG instance "
                    "%s (ID: %s) is failed, cause: %s (status code: %s)",
                    instance_name, instance_id, e.error_msg, e.status_code)
                raise
            except Exception as e:
                log.error(
                    "[filters]- The filter:[log-analysis-unable] "
                    "query the service:[list_features_v2] unexpected error while querying "
                    "features for APIG instance %s (ID: %s): %s",
                    instance_name, instance_id, str(e), exc_info=True)
                raise

        return matched_resources


@ApigInstanceResource.filter_registry.register('custom-log-enable')
class CustomLogEnableFilter(Filter):
    """Filter APIG instances where custom_log feature is enabled

    This filter checks if the custom_log feature is enabled in the instance's features.

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-instance-custom-log-enable
            resource: huaweicloud.apig-instance
            filters:
              - type: custom-log-enable
    """

    schema = type_schema('custom-log-enable')

    def process(self, resources, event=None):
        """
        Process resources to filter APIG instances where custom_log feature is enabled

        :param resources: List of APIG instance resources
        :param event: Optional event data
        :return: Filtered list of resources matching the criteria
        """
        client = local_session(self.manager.session_factory).client("apig-instance")
        matched_resources = []

        for resource in resources:
            instance_id = resource.get('id')
            instance_name = resource.get('instance_name', 'Unknown')

            try:
                # Query instance features list
                request = ListFeaturesV2Request(instance_id=instance_id, limit=500)
                response = client.list_features_v2(request)

                # Find custom_log feature in the features list
                custom_log_feature = None
                if response.features:
                    for feature in response.features:
                        if feature.name == 'custom_log':
                            custom_log_feature = feature
                            break

                # If custom_log feature is found and enabled, add to matched resources
                if custom_log_feature and custom_log_feature.enable:
                    matched_resources.append(resource)
                    log.info(
                        "[filters]- The filter:[custom-log-enable] "
                        "query the service:[list_features_v2] instance %s "
                        "(ID: %s) has custom_log feature enabled",
                        instance_name, instance_id)
                else:
                    log.info(
                        "[filters]- The filter:[custom-log-enable] "
                        "query the service:[list_features_v2] instance %s "
                        "(ID: %s) does not have custom_log feature enabled or feature not found",
                        instance_name, instance_id)

            except exceptions.ClientRequestException as e:
                log.error(
                    "[filters]- The filter:[custom-log-enable] "
                    "query the service:[list_features_v2] query features for APIG instance "
                    "%s (ID: %s) is failed, cause: %s (status code: %s)",
                    instance_name, instance_id, e.error_msg, e.status_code)
                raise
            except Exception as e:
                log.error(
                    "[filters]- The filter:[custom-log-enable] "
                    "query the service:[list_features_v2] unexpected error while querying "
                    "features for APIG instance %s (ID: %s): %s",
                    instance_name, instance_id, str(e), exc_info=True)
                raise

        return matched_resources


@ApigInstanceResource.filter_registry.register('backend-client-certificate-unable')
class BackendClientCertificateUnableFilter(Filter):
    """Filter APIG instances where backend client certificate is disabled

    This filter identifies APIG instances where the backend client certificate
    feature is configured but disabled (enable field in config is "off").

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-instance-backend-client-certificate-unable
            resource: huaweicloud.apig-instance
            filters:
              - type: backend-client-certificate-unable
    """

    schema = type_schema('backend-client-certificate-unable')

    def process(self, resources, event=None):
        """
        Process resources to filter APIG instances where backend client certificate is disabled

        :param resources: List of APIG instance resources
        :param event: Optional event data
        :return: Filtered list of resources matching the criteria
        """
        client = local_session(self.manager.session_factory).client("apig-instance")
        matched_resources = []

        for resource in resources:
            instance_id = resource.get('id')
            instance_name = resource.get('instance_name', 'Unknown')

            try:
                # Query instance features list
                request = ListFeaturesV2Request(instance_id=instance_id, limit=500)
                response = client.list_features_v2(request)

                # Find backend_client_certificate feature in the features list
                backend_cert_feature = None
                if response.features:
                    for feature in response.features:
                        if feature.name == 'backend_client_certificate':
                            backend_cert_feature = feature
                            break

                # If backend_client_certificate feature is not found, skip this instance
                if backend_cert_feature is None:
                    log.warning(
                        "[filters]- The filter:[backend-client-certificate-unable] "
                        "query the service:[list_features_v2] instance %s "
                        "(ID: %s) does not have backend_client_certificate feature configured",
                        instance_name, instance_id)
                    continue

                # Parse config field (it's a JSON string)
                config_str = backend_cert_feature.config
                if not config_str:
                    # If config is empty, skip this instance
                    log.warning(
                        "[filters]- The filter:[backend-client-certificate-unable] "
                        "query the service:[list_features_v2] instance %s "
                        "(ID: %s) backend_client_certificate feature config is empty",
                        instance_name, instance_id)
                    continue

                try:
                    # Parse JSON config string
                    config_dict = json.loads(config_str)
                    # Check if enable field in config is "off"
                    enable_value = config_dict.get('enable', '')
                    if enable_value == 'off':
                        matched_resources.append(resource)
                        log.info(
                            "[filters]- The filter:[backend-client-certificate-unable] "
                            "query the service:[list_features_v2] instance %s "
                            "(ID: %s) backend_client_certificate feature is disabled. "
                            "Config: %s", instance_name, instance_id, config_str)
                except json.JSONDecodeError as e:
                    log.error(
                        "[filters]- The filter:[backend-client-certificate-unable] "
                        "query the service:[list_features_v2] instance %s "
                        "(ID: %s) backend_client_certificate feature config is not valid JSON: "
                        "%s. Config: %s", instance_name, instance_id, e, config_str)
                    raise

            except exceptions.ClientRequestException as e:
                log.error(
                    "[filters]- The filter:[backend-client-certificate-unable] "
                    "query the service:[list_features_v2] query features for APIG instance "
                    "%s (ID: %s) is failed, cause: %s (status code: %s)",
                    instance_name, instance_id, e.error_msg, e.status_code)
                raise
            except Exception as e:
                log.error(
                    "[filters]- The filter:[backend-client-certificate-unable] "
                    "query the service:[list_features_v2] unexpected error while querying "
                    "features for APIG instance %s (ID: %s): %s",
                    instance_name, instance_id, str(e), exc_info=True)
                raise

        return matched_resources


@ApigInstanceResource.action_registry.register('enable-log-analysis')
class EnableLogAnalysisAction(HuaweiCloudBaseAction):
    """Enable log analysis feature for APIG instance

    This action enables the log analysis feature for an APIG instance by setting
    the log group and topic names.

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-instance-enable-log-analysis
            resource: huaweicloud.apig-instance
            actions:
              - type: enable-log-analysis
                log_group_name: lts-group-ps8e
                log_topic_name: lts-topic-q0vz
    """

    schema = type_schema(
        'enable-log-analysis',
        log_group_name={'type': 'string', 'required': True},
        log_topic_name={'type': 'string', 'required': True}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        instance_id = resource['id']

        try:
            # Build feature toggle object with log analysis configuration
            feature_toggle = FeatureToggle(
                name='lts',
                enable=True
            )

            # Construct config JSON string
            log_group_name = self.data['log_group_name']
            log_topic_name = self.data['log_topic_name']
            log_group_id, log_stream_id = self.get_group_and_stream_id_by_name(
                log_group_name, log_topic_name
            )
            config = {
                "log_group": log_group_name,
                "log_stream": log_topic_name,
                "group_id": log_group_id,
                "topic_id": log_stream_id,
            }
            feature_toggle.config = json.dumps(config)

            # Create request
            request = CreateFeatureV2Request(
                instance_id=instance_id,
                body=feature_toggle
            )

            # Send request
            response = client.create_feature_v2(request)
            instance_name = resource.get('instance_name', instance_id)
            log.info(
                "[actions]- [enable-log-analysis] The resource:[apig-instance] "
                "with key:[%s/%s] enable log analysis is success.",
                instance_name, instance_id)

            return response
        except exceptions.ClientRequestException as e:
            instance_name = resource.get('instance_name', instance_id)
            log.error(
                "[actions]- [enable-log-analysis] The resource:[apig-instance] "
                "with key:[%s/%s] enable log analysis is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                instance_name, instance_id,
                e.status_code, e.request_id, e.error_code, e.error_msg)
            raise

    def get_group_and_stream_id_by_name(self, group_name, stream_name):
        lts_client_v2 = local_session(self.manager.session_factory).client("lts-stream")
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


# API Resource Management
@resources.register('apig-api')
class ApiResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway API Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-api'
        enum_spec = ('list_apis_v2', 'apis', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = False

    def get_instance_id(self):
        """
        Query and get API Gateway instance ID
        """
        session = local_session(self.session_factory)

        # If instance_id is specified in the policy, use it directly
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(
                "The resource:[apig-api] using instance_id from policy "
                "configuration: %s", instance_id)
            return [instance_id]

        # Query APIG instance list
        try:
            # Use apig-instance service client
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request(limit=500)
            response = client.list_instances_v2(instances_request)

            if hasattr(response, 'instances') and response.instances:
                instance_ids = []
                for instance in response.instances:
                    instance_ids.append(instance.id)
                return instance_ids
        except Exception as e:
            log.error(
                "The resource:[apig-api] query APIG instance list is failed, "
                "cause: %s", str(e), exc_info=True)
            raise

        return []

    def get_resources(self, resource_ids):
        resources = self.get_api_resources()
        result = []
        for resource in resources:
            if resource["id"] in resource_ids:
                result.append(resource)
        return result

    def _fetch_resources(self, query):
        return self.get_api_resources()

    def get_api_resources(self):
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Get instance ID
        instance_ids = self.get_instance_id()

        resources = []
        for instance_id in instance_ids:
            offset, limit = 0, 500
            while True:
                # Create new request object instead of modifying the incoming query
                request = ListApisV2Request(offset=offset, limit=limit)
                request.instance_id = instance_id

                # Call client method to process request
                try:
                    response = client.list_apis_v2(request)
                    resource = safe_json_parse(response.apis)
                    for item in resource:
                        item["instance_id"] = instance_id
                    resources = resources + resource
                except exceptions.ClientRequestException as e:
                    log.error(
                        "The resource:[apig-api] query API list is failed, "
                        "cause: %s", str(e), exc_info=True)
                    raise

                offset += limit
                if not response.total or offset >= response.total:
                    break

        return resources


@ApiResource.filter_registry.register('in-default-group')
class InDefaultGroupFilter(Filter):
    """Filter API resources that belong to the default group

    This filter checks if an API belongs to the default group by querying the group details.

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-api-in-default-group
            resource: huaweicloud.apig-api
            filters:
              - type: in-default-group
    """

    schema = type_schema('in-default-group')

    def process(self, resources, event=None):
        """
        Process resources to filter APIs belonging to the default group

        :param resources: List of API resources
        :param event: Optional event data
        :return: Filtered list of resources matching the criteria
        """
        client = local_session(self.manager.session_factory).client("apig-api")
        matched_resources = []

        for resource in resources:
            api_id = resource.get('id')
            instance_id = resource.get('instance_id')
            api_name = resource.get('name', 'Unknown')

            if not api_id or not instance_id:
                log.warning(
                    "[filters]- The filter:[in-default-group] "
                    "query the service:[show_details_of_api_v2] skipping API %s "
                    "due to missing api_id or instance_id", api_name)
                continue

            try:
                # Query API details to get group_id
                request = ShowDetailsOfApiV2Request(
                    instance_id=instance_id,
                    api_id=api_id
                )
                api_response = client.show_details_of_api_v2(request)
                api_details = safe_json_parse(api_response)

                group_id = api_details.get('group_id')
                if not group_id:
                    log.warning(
                        "[filters]- The filter:[in-default-group] "
                        "query the service:[show_details_of_api_v2] API %s "
                        "(ID: %s) does not have a group_id", api_name, api_id)
                    continue

                # Query group details to check if it's the default group
                request = ShowDetailsOfApiGroupV2Request(
                    instance_id=instance_id,
                    group_id=group_id
                )
                group_response = client.show_details_of_api_group_v2(request)
                group_details = safe_json_parse(group_response)

                if group_details.get('is_default') == 1:
                    matched_resources.append(resource)
                    log.info(
                        "[filters]- The filter:[in-default-group] "
                        "query the service:[show_details_of_api_group_v2] API %s "
                        "(ID: %s) belongs to the default group (Group ID: %s)",
                        api_name, api_id, group_id)
                else:
                    log.info(
                        "[filters]- The filter:[in-default-group] "
                        "query the service:[show_details_of_api_group_v2] API %s "
                        "(ID: %s) does not belong to the default group (Group ID: %s)",
                        api_name, api_id, group_id)

            except exceptions.ClientRequestException as e:
                log.error(
                    "[filters]- The filter:[in-default-group] "
                    "query the service:[show_details_of_api_v2] query details for API %s "
                    "(ID: %s) is failed, cause: %s (status code: %s)",
                    api_name, api_id, e.error_msg, e.status_code)
                raise
            except Exception as e:
                log.error(
                    "[filters]- The filter:[in-default-group] "
                    "query the service:[show_details_of_api_v2] unexpected error while "
                    "processing API %s (ID: %s): %s",
                    api_name, api_id, str(e), exc_info=True)
                raise

        return matched_resources


# API Resource Actions
@ApiResource.action_registry.register('delete')
class DeleteApiAction(HuaweiCloudBaseAction):
    """Delete API action

    :example:
    Define a policy to delete API Gateway APIs with name 'test-api':

    .. code-block:: yaml

        policies:
          - name: apig-api-delete
            resource: huaweicloud.apig-api
            filters:
              - type: value
                key: name
                value: test-api
            actions:
              - delete
    """
    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        api_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            api_name = resource.get('name', 'unknown')
            log.error(
                "[actions]- [delete] The resource:[apig-api] "
                "with key:[%s/%s] delete API is failed, "
                "cause: No available instance found", api_name, api_id)
            return

        try:
            # Ensure instance_id is string type
            request = DeleteApiV2Request(
                instance_id=instance_id,
                api_id=api_id
            )

            client.delete_api_v2(request)
            api_name = resource.get('name', api_id)
            log.info(
                "[actions]- [delete] The resource:[apig-api] "
                "with key:[%s/%s] delete API is success.",
                api_name, api_id)
        except exceptions.ClientRequestException as e:
            api_name = resource.get('name', api_id)
            log.error(
                "[actions]- [delete] The resource:[apig-api] "
                "with key:[%s/%s] delete API is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                api_name, api_id, e.status_code, e.request_id, e.error_code, e.error_msg)
            raise


@ApiResource.action_registry.register('offline-and-delete')
class OfflineAndDeleteApiAction(HuaweiCloudBaseAction):
    """Offline and delete API action

    This action first checks if the API is published, if yes, it will unpublish
    the API before deletion.

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-api-offline-and-delete
            resource: huaweicloud.apig-api
            filters:
              - type: value
                key: name
                value: test-api
            actions:
              - offline-and-delete
    """

    schema = type_schema('offline-and-delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        api_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            api_name = resource.get('name', 'unknown')
            log.error(
                "[actions]- [offline-and-delete] The resource:[apig-api] "
                "with key:[%s/%s] offline-and-delete API is failed, "
                "cause: No available instance found", api_name, api_id)
            return

        try:
            # Query api details to check if it's published
            request = ShowDetailsOfApiV2Request(
                instance_id=instance_id,
                api_id=api_id
            )
            api_response = client.show_details_of_api_v2(request)
            api_details = safe_json_parse(api_response)

            run_env_id = api_details.get('run_env_id')
            if run_env_id != "":
                # Offline the API
                from huaweicloudsdkapig.v2.model.api_action_info import ApiActionInfo

                offline_request = CreateOrDeletePublishRecordForApiV2Request(
                    instance_id=instance_id,
                    body=ApiActionInfo(api_id=api_id, env_id=run_env_id, action='offline')
                )
                client.create_or_delete_publish_record_for_api_v2(offline_request)
                api_name = api_details.get('name', api_id)
                log.info(
                    "[actions]- [offline-and-delete] The resource:[apig-api] "
                    "with key:[%s/%s] offline API is success.",
                    api_name, api_id)

            # Delete the API
            delete_request = DeleteApiV2Request(
                instance_id=instance_id,
                api_id=api_id
            )
            client.delete_api_v2(delete_request)
            api_name = api_details.get('name', api_id)
            log.info(
                "[actions]- [offline-and-delete] The resource:[apig-api] "
                "with key:[%s/%s] delete API is success.",
                api_name, api_id)

        except exceptions.ClientRequestException as e:
            api_name = resource.get('name', api_id)
            log.error(
                "[actions]- [offline-and-delete] The resource:[apig-api] "
                "with key:[%s/%s] offline and delete API is failed, cause: %s",
                api_name, api_id, e, exc_info=True)
            raise


@ApiResource.action_registry.register('update')
class UpdateApiAction(HuaweiCloudBaseAction):
    """Update API action

    This action allows updating various properties of an API in API Gateway,
    including name, request protocol, request method, request URI, authentication type, etc.

    :example:
    Define a policy to update an API Gateway API with comprehensive configuration options:

    .. code-block:: yaml

        policies:
            - name: apig-api-update-full-example
              resource: huaweicloud.apig-api
              filters:
                - type: value
                  key: id
                  value: 499e3bd193ba4db89a49f0ebdef19796
              actions:
                - type: update
                  # Basic API properties
                  name: updated-api-name
                  api_type: 1  # 1 for public API, 2 for private API
                  version: "v1.0.1"
                  req_protocol: HTTPS
                  req_method: POST
                  req_uri: "/v1/test/update"
                  auth_type: APP  # Options: NONE, APP, IAM, AUTHORIZER
                  group_id: "c77f5e81d9cb4424bf704ef2b0ac7600"
                  match_mode: "NORMAL"  # NORMAL or SWA
                  cors: false
                  remark: "Updated API with complete parameters"

                  # Response examples
                  result_normal_sample: '{"result": "success", "data": {"id": 1}}'

                  # Tracing configuration
                  trace_enabled: true
                  sampling_strategy: "RATE"
                  sampling_param: "10"

                  # Tags
                  tags:
                    - "production"
                    - "api-gateway"

                  # Backend API configuration
                  backend_type: "HTTP"  # HTTP, FUNCTION, or MOCK
                  backend_api:
                    req_protocol: "HTTPS"
                    req_method: "POST"
                    req_uri: "/backend/service"
                    timeout: 5000
                    retry_count: "3"
                    url_domain: "api.example.com"
                    host: "api.backend-service.com"

                  # Backend parameters
                  backend_params:
                    - name: "X-User-Id"
                      value: "$context.authorizer.userId"
                      location: "HEADER"
                      origin: "SYSTEM"
                      remark: "User ID from the authorizer"
                    - name: "api-version"
                      value: "v1"
                      location: "HEADER"
                      origin: "CONSTANT"
                      remark: "API version as a constant"

                  # Authentication options
                  auth_opt:
                    app_code_auth_type: "HEADER"
                    app_code_headers:
                      - "X-Api-Auth"

                  # SSL verification
                  disables_ssl_verification: false

                  # Mock response (when backend_type is MOCK)
                  mock_info:
                    status_code: 200
                    example: '{"data": "mock response"}'
                    contentType: "application/json"
    """

    schema = type_schema(
        'update',
        name={'type': 'string'},
        # Use api_type instead of type to avoid conflict with operation type
        api_type={'type': 'integer', 'enum': [1, 2]},
        req_protocol={'type': 'string', 'enum': [
            'HTTP', 'HTTPS', 'BOTH', 'GRPCS']},
        req_method={'type': 'string', 'enum': [
            'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'PATCH', 'OPTIONS', 'ANY']},
        req_uri={'type': 'string'},
        auth_type={'type': 'string', 'enum': [
            'NONE', 'APP', 'IAM', 'AUTHORIZER']},
        backend_type={'type': 'string', 'enum': ['HTTP', 'FUNCTION', 'MOCK']},
        group_id={'type': 'string'},
        version={'type': 'string'},
        cors={'type': 'boolean'},
        remark={'type': 'string'},
        authorizer_id={'type': 'string'},
        match_mode={'type': 'string', 'enum': ['NORMAL', 'SWA']},
        result_normal_sample={'type': 'string'},
        result_failure_sample={'type': 'string'},
        trace_enabled={'type': 'boolean'},
        sampling_strategy={'type': 'string'},
        sampling_param={'type': 'string'},
        tags={'type': 'array', 'items': {'type': 'string'}},
        backend_api={'type': 'object', 'properties': {
            'req_protocol': {'type': 'string', 'enum': ['HTTP', 'HTTPS']},
            'req_method': {'type': 'string', 'enum': [
                'GET', 'POST', 'PUT', 'DELETE', 'HEAD', 'PATCH', 'OPTIONS', 'ANY']},
            'req_uri': {'type': 'string'},
            'timeout': {'type': 'integer'},
            'retry_count': {'type': 'string'},
            'url_domain': {'type': 'string'},
            'host': {'type': 'string'},
            'vpc_channel_info': {'type': 'object'}
        }},
        backend_params={'type': 'array', 'items': {'type': 'object', 'properties': {
            'name': {'type': 'string'},
            'value': {'type': 'string'},
            'location': {'type': 'string', 'enum': [
                'PATH', 'QUERY', 'HEADER']},
            'origin': {'type': 'string', 'enum': [
                'REQUEST', 'CONSTANT', 'SYSTEM']},
            'remark': {'type': 'string'}
        }}},
        auth_opt={'type': 'object', 'properties': {
            'app_code_auth_type': {'type': 'string', 'enum': [
                'DISABLE', 'HEADER', 'APP_CODE', 'HEADER_OR_APP_CODE']},
            'app_code_headers': {'type': 'array', 'items': {'type': 'string'}}
        }},
        disables_ssl_verification={'type': 'boolean'},
        mock_info={'type': 'object', 'properties': {
            'status_code': {'type': 'integer'},
            'example': {'type': 'string'},
            'contentType': {'type': 'string'}
        }}
    )

    def _build_update_body(self, resource):
        """Build API update request body

        Construct API update request body based on policy parameters while preserving
        necessary fields from the original API

        :param resource: API resource dictionary
        :return: Update request body object
        """
        from huaweicloudsdkapig.v2.model.api_create import ApiCreate

        # Extract necessary fields from the original API to ensure critical information is preserved
        update_info = {}

        for field in self.data:
            if field == "api_type":
                update_info["type"] = self.data[field]
            else:
                update_info[field] = self.data[field]

        # Construct API create request body
        return ApiCreate(**update_info)

    def perform_action(self, resource):
        client = self.manager.get_client()
        api_id = resource['id']
        instance_id = resource.get('instance_id')

        try:
            api_name = resource.get('name', api_id)
            log.info(
                "[actions]- [update] The resource:[apig-api] "
                "with key:[%s/%s] updating API (Instance: %s)",
                api_name, api_id, instance_id)

            # First build the parameters to update
            update_body = self._build_update_body(resource)

            if not update_body:
                api_name = resource.get('name', api_id)
                log.error(
                    "[actions]- [update] The resource:[apig-api] "
                    "with key:[%s/%s] update API is failed, "
                    "cause: No update parameters provided", api_name, api_id)
                return

            # Create update request, ensure instance_id is string type
            request = UpdateApiV2Request(
                instance_id=instance_id,
                api_id=api_id,
                body=update_body
            )

            # Print request object
            log.debug(
                "[actions]- [update] The resource:[apig-api] request object: %s", request)

            # Send request
            response = client.update_api_v2(request)
            api_name = resource.get('name', api_id)
            log.info(
                "[actions]- [update] The resource:[apig-api] "
                "with key:[%s/%s] update API is success.",
                api_name, api_id)
            return response
        except exceptions.ClientRequestException as e:
            api_name = resource.get('name', api_id)
            log.error(
                "[actions]- [update] The resource:[apig-api] "
                "with key:[%s/%s] update API is failed, cause: %s",
                api_name, api_id, e, exc_info=True)
            raise


@ApiResource.action_registry.register('update-to-https')
class UpdateToHttps(HuaweiCloudBaseAction):
    """Update API request protocol to HTTPS

    This action reads API id from event's cts.response field and updates
    the API's req_protocol to HTTPS if it's currently HTTP or BOTH.

    :example:
    Define a policy to update API protocol to HTTPS when triggered by an event:

    .. code-block:: yaml

        policies:
          - name: apig-api-update-to-https
            resource: huaweicloud.apig-api
            mode:
              type: cloudtrace
              xrole: admin
              events:
                - source: "APIG.Api"
                  event: "createApi"
                  code: 201
                  ids: "response.id"
                - source: "APIG.Api"
                  event: "updateApi"
                  code: 200
                  ids: "response.id"
            actions:
              - type: update-to-https
    """

    schema = type_schema('update-to-https')

    def perform_action(self, resource):
        api_id = resource['id']
        instance_id = resource.get('instance_id')

        if not api_id:
            log.error(
                "[actions]- [update-to-https] The resource:[apig-api] "
                "update API to HTTPS is failed, cause: No API ID found in resource")
            return self.process_result([])

        if not instance_id:
            log.error(
                "[actions]- [update-to-https] The resource:[apig-api] "
                "update API to HTTPS is failed, cause: No instance_id available")
            return self.process_result([])

        try:
            client = self.manager.get_client()

            # Query api details to check if it's published
            request = ShowDetailsOfApiV2Request(
                instance_id=instance_id,
                api_id=api_id
            )
            api_response = client.show_details_of_api_v2(request)
            api_details = safe_json_parse(api_response)

            # Check current req_protocol
            req_protocol = api_details.get('req_protocol')
            api_name = api_details.get('name', api_id)
            if req_protocol not in ('HTTP', 'BOTH'):
                log.info(
                    "[actions]- [update-to-https] The resource:[apig-api] "
                    "with key:[%s/%s] req_protocol is %s, no update needed",
                    api_name, api_id, req_protocol)
                return self.process_result([])

            log.info(
                "[actions]- [update-to-https] The resource:[apig-api] "
                "with key:[%s/%s] updating req_protocol from %s to HTTPS",
                api_name, api_id, req_protocol)

            from huaweicloudsdkapig.v2.model.api_create import ApiCreate

            # Build update body from api_details, only including fields that ApiCreate accepts
            # Get all valid field names from ApiCreate.openapi_types
            valid_fields = set(ApiCreate.openapi_types.keys())

            update_info = {}
            # Only copy fields that are valid for ApiCreate
            for key, value in api_details.items():
                if key in valid_fields:
                    update_info[key] = value

            # Override req_protocol to HTTPS
            update_info['req_protocol'] = 'HTTPS'

            # Build API create request body
            update_body = ApiCreate(**update_info)

            # Create update request
            request = UpdateApiV2Request(
                instance_id=instance_id,
                api_id=api_id,
                body=update_body
            )

            log.info(
                "[actions]- [update-to-https] The resource:[apig-api] "
                "update request: instance_id=%s, api_id=%s", instance_id, api_id)

            # Send update request
            client.update_api_v2(request)
            api_name = api_details.get('name', api_id)
            log.info(
                "[actions]- [update-to-https] The resource:[apig-api] "
                "with key:[%s/%s] update req_protocol to HTTPS is success.",
                api_name, api_id)

            return self.process_result([{'id': api_id, 'name': api_name}])

        except exceptions.ClientRequestException as e:
            api_name = api_details.get('name', api_id)
            log.error(
                "[actions]- [update-to-https] The resource:[apig-api] "
                "with key:[%s/%s] update API to HTTPS is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                api_name, api_id, e.status_code, e.request_id,
                e.error_code, e.error_msg, exc_info=True)
            raise
        except Exception as e:
            api_name = api_details.get('name', api_id)
            log.error(
                "[actions]- [update-to-https] The resource:[apig-api] "
                "with key:[%s/%s] update API to HTTPS is failed, cause: %s",
                api_name, api_id, str(e), exc_info=True)
            raise


# Environment Resource Management
@resources.register('apig-stage')
class StageResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway Environment Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-stage'
        enum_spec = ('list_environments_v2', 'envs', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = False

    def get_instance_id(self):
        """
        Query and get API Gateway instance ID
        """
        session = local_session(self.session_factory)

        # If instance_id is specified in the policy, use it directly
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(
                "The resource:[apig-stage] using instance_id from policy "
                "configuration: %s", instance_id)
            return [instance_id]

        # Query APIG instance list
        try:
            # Use apig-instance service client
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request(limit=500)
            response = client.list_instances_v2(instances_request)

            if hasattr(response, 'instances') and response.instances:
                instance_ids = []
                for instance in response.instances:
                    instance_ids.append(instance.id)
                return instance_ids
        except Exception as e:
            log.error(
                "The resource:[apig-stage] query APIG instance list is failed, "
                "cause: %s", str(e), exc_info=True)
            raise

        return []

    def get_resources(self, resource_ids):
        resources = self.get_stage_resources()
        result = []
        for resource in resources:
            if resource["id"] in resource_ids:
                result.append(resource)
        return result

    def _fetch_resources(self, query):
        return self.get_stage_resources()

    def get_stage_resources(self):
        """Override resource retrieval method to ensure
           instance_id parameter is included in the request"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Get instance ID
        instance_ids = self.get_instance_id()

        resources = []
        for instance_id in instance_ids:
            # Create new request object instead of modifying the incoming query
            request = ListEnvironmentsV2Request(limit=500)
            request.instance_id = instance_id

            # Call client method to process request
            try:
                response = client.list_environments_v2(request)
                resource = safe_json_parse(response.envs)
                for item in resource:
                    item["instance_id"] = instance_id
                resources = resources + resource

                return resources
            except exceptions.ClientRequestException as e:
                log.error(
                    "The resource:[apig-stage] query environment list is failed, "
                    "cause: %s", str(e), exc_info=True)
                raise
        return resources


# Update Environment Resource
@StageResource.action_registry.register('update')
class UpdateStageAction(HuaweiCloudBaseAction):
    """Update environment action

    :example:
    Define a policy to update an API Gateway environment's name and description:

    .. code-block:: yaml

        policies:
          - name: apig-stage-update
            resource: huaweicloud.apig-stage
            filters:
              - type: value
                key: name
                value: TEST
            actions:
              - type: update
                name: updated-stage-name
                remark: updated description
    """

    schema = type_schema(
        'update',
        name={'type': 'string'},
        remark={'type': 'string'},
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        env_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            env_name = resource.get('name', 'unknown')
            log.error(
                "[actions]- [update] The resource:[apig-stage] "
                "with key:[%s/%s] update environment is failed, "
                "cause: No available instance found", env_name, env_id)
            return

        try:
            env_name = resource.get('name', env_id)
            log.info(
                "[actions]- [update] The resource:[apig-stage] "
                "with key:[%s/%s] updating environment (Instance: %s)",
                env_name, env_id, instance_id)

            # Prepare update parameters
            update_info = {}

            if 'name' in self.data:
                update_info['name'] = self.data['name']
            if 'remark' in self.data:
                update_info['remark'] = self.data['remark']

            # Create update request, ensure instance_id is string type
            request = UpdateEnvironmentV2Request(
                instance_id=instance_id,
                env_id=env_id,
                body=update_info
            )

            # Print request object
            log.debug(
                "[actions]- [update] The resource:[apig-stage] request object: %s", request)

            # Send request
            response = client.update_environment_v2(request)
            env_name = resource.get('name', env_id)
            log.info(
                "[actions]- [update] The resource:[apig-stage] "
                "with key:[%s/%s] update environment is success.",
                env_name, env_id)
            return response
        except exceptions.ClientRequestException as e:
            env_name = resource.get('name', env_id)
            log.error(
                "[actions]- [update] The resource:[apig-stage] "
                "with key:[%s/%s] update environment is failed, cause: %s",
                env_name, env_id, e, exc_info=True)
            raise


@StageResource.action_registry.register('delete')
class DeleteStageAction(HuaweiCloudBaseAction):
    """Delete environment action

    :example:
    Define a policy to delete API Gateway environments with name 'TEST':

    .. code-block:: yaml

        policies:
          - name: apig-stage-delete
            resource: huaweicloud.apig-stage
            filters:
              - type: value
                key: name
                value: TEST
            actions:
              - delete
    """

    schema = type_schema('delete')

    def perform_action(self, resource):
        client = self.manager.get_client()
        env_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            env_name = resource.get('name', 'unknown')
            log.error(
                "[actions]- [delete] The resource:[apig-stage] "
                "with key:[%s/%s] delete environment is failed, "
                "cause: No available instance found", env_name, env_id)
            return

        try:
            env_name = resource.get('name', env_id)
            log.info(
                "[actions]- [delete] The resource:[apig-stage] "
                "with key:[%s/%s] deleting environment (Instance: %s)",
                env_name, env_id, instance_id)

            # Ensure instance_id is string type
            request = DeleteEnvironmentV2Request(
                instance_id=instance_id,
                env_id=env_id
            )

            # Print request object
            log.debug(
                "[actions]- [delete] The resource:[apig-stage] request object: %s", request)

            client.delete_environment_v2(request)
            env_name = resource.get('name', env_id)
            log.info(
                "[actions]- [delete] The resource:[apig-stage] "
                "with key:[%s/%s] delete environment is success.",
                env_name, env_id)
        except exceptions.ClientRequestException as e:
            env_name = resource.get('name', env_id)
            log.error(
                "[actions]- [delete] The resource:[apig-stage] "
                "with key:[%s/%s] delete environment is failed, cause: %s",
                env_name, env_id, e, exc_info=True)
            raise


# API Group Resource Management
@resources.register('apig-api-groups')
class ApiGroupResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway Group Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-api-groups'
        enum_spec = ('list_api_groups_v2', 'groups', 'offset')
        id = 'id'
        name = 'name'
        filter_name = 'name'
        filter_type = 'scalar'
        taggable = False

    def get_instance_id(self):
        """
        Query and get API Gateway instance ID
        """
        session = local_session(self.session_factory)

        # If instance_id is specified in the policy, use it directly
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(
                "The resource:[apig-api-groups] using instance_id from policy "
                "configuration: %s", instance_id)
            return [instance_id]

        # Query APIG instance list
        try:
            # Use apig-instance service client
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request(limit=500)
            response = client.list_instances_v2(instances_request)

            if hasattr(response, 'instances') and response.instances:
                instance_ids = []
                for instance in response.instances:
                    instance_ids.append(instance.id)
                return instance_ids
        except Exception as e:
            log.error(
                "The resource:[apig-api-groups] query APIG instance list is failed, "
                "cause: %s", str(e), exc_info=True)
            raise

        return []

    def get_resources(self, resource_ids):
        resources = self.get_api_groups_resources()
        result = []
        for resource in resources:
            if resource["id"] in resource_ids:
                result.append(resource)
        return result

    def _fetch_resources(self, query):
        return self.get_api_groups_resources()

    def get_api_groups_resources(self):
        """Override resource retrieval method to ensure
           instance_id parameter is included in the request"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Get instance ID
        instance_ids = self.get_instance_id()

        resources = []
        for instance_id in instance_ids:
            offset, limit = 0, 500
            while True:
                # Create new request object instead of modifying the incoming query
                request = ListApiGroupsV2Request(offset=offset, limit=limit)
                request.instance_id = instance_id

                # Call client method to process request
                try:
                    response = client.list_api_groups_v2(request)
                    resource = safe_json_parse(response.groups)
                    for item in resource:
                        item["instance_id"] = instance_id
                    resources = resources + resource
                except exceptions.ClientRequestException as e:
                    log.error(
                        "The resource:[apig-api-groups] query API Group list is failed, "
                        "cause: %s", str(e), exc_info=True)
                    raise

                offset += limit
                if not response.total or offset >= response.total:
                    break

        return resources


# Update Security
@ApiGroupResource.action_registry.register('update-domain')
class UpdateDomainSecurityAction(HuaweiCloudBaseAction):
    """Update domain security policy action

    :example:
    Define a policy to update security settings for an API Gateway domain:

    .. code-block:: yaml

        policies:
          - name: apig-domain-update-domain
            resource: huaweicloud.apig-api-groups
            filters:
              - type: value
                key: id
                value: c77f5e81d9cb4424bf704ef2b0ac7600
            actions:
              - type: update-domain
                domain_id: test_domain_id
                min_ssl_version: TLSv1.2
    """

    schema = type_schema(
        'update-domain',
        min_ssl_version={'type': 'string', 'enum': ['TLSv1.1', 'TLSv1.2']},
        is_http_redirect_to_https={'type': 'boolean'},
        verified_client_certificate_enabled={'type': 'boolean'},
        ingress_http_port={'type': 'integer', 'minimum': -1, 'maximum': 49151},
        ingress_https_port={'type': 'integer',
                            'minimum': -1, 'maximum': 49151},
        domain_id={'type': 'string'}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        group_id = resource['id']
        instance_id = resource.get('instance_id')

        # Get domain_id from policy data
        domain_id = self.data.get('domain_id')

        if not domain_id:
            group_name = resource.get('name', 'unknown')
            log.error(
                "[actions]- [update-domain] The resource:[apig-api-groups] "
                "with key:[%s/%s] update domain security policy is failed, "
                "cause: No domain_id specified", group_name, group_id)
            return

        try:
            group_name = resource.get('name', group_id)
            log.info(
                "[actions]- [update-domain] The resource:[apig-api-groups] "
                "with key:[%s/%s] updating domain security policy "
                "(Domain ID: %s, Instance: %s)",
                group_name, group_id, domain_id, instance_id)

            from huaweicloudsdkapig.v2.model.url_domain_modify import UrlDomainModify

            update_info = {}

            # Required fields from original resource
            for field in self.data:
                if field != "domain_id" and field != "type":
                    update_info[field] = self.data[field]

            # Create update request, ensure instance_id is string type
            request = UpdateDomainV2Request(
                instance_id=instance_id,
                domain_id=domain_id,
                body=UrlDomainModify(**update_info)
            )

            # Print request object
            log.debug(
                "[actions]- [update-domain] The resource:[apig-api-groups] "
                "request object: %s", request)

            # Send request
            response = client.update_domain_v2(request)
            group_name = resource.get('name', group_id)
            log.info(
                "[actions]- [update-domain] The resource:[apig-api-groups] "
                "with key:[%s/%s] update domain security policy is success "
                "(Domain ID: %s).", group_name, group_id, domain_id)
            return response
        except exceptions.ClientRequestException as e:
            group_name = resource.get('name', group_id)
            log.error(
                "[actions]- [update-domain] The resource:[apig-api-groups] "
                "with key:[%s/%s] update domain security policy is failed "
                "(Domain ID: %s), cause: %s",
                group_name, group_id, domain_id, e, exc_info=True)
            raise


@ApiGroupResource.action_registry.register('update-to-tls-v1.2-from-event')
class UpdateToTlsV12FromEvent(HuaweiCloudBaseAction):
    """Update domain min_ssl_version to TLSv1.2 from event

    This action reads domain information from event's cts.response field and updates
    the domain's min_ssl_version to TLSv1.2 if it's currently TLSv1.1.

    :example:
    Define a policy to update domain SSL version to TLSv1.2 when triggered by an event:

    .. code-block:: yaml

        policies:
          - name: apig-api-groups-update-to-tls-v1.2-from-event
            resource: huaweicloud.apig-api-groups
            mode:
              type: cloudtrace
              xrole: admin
              events:
                - source: "APIG.ApiGroup"
                  event: "createDomainBinding"
                  code: 201
                  ids: "resource_id"
                - source: "APIG.ApiGroup"
                  event: "modifySecureTransmission"
                  code: 200
                  ids: "resource_id"
            actions:
              - type: update-to-tls-v1.2-from-event
    """

    schema = type_schema('update-to-tls-v1.2-from-event')

    def process(self, event):
        """
        Process event to update domain min_ssl_version to TLSv1.2

        :param event: Event data containing cts.response with domain information
        :return: Result of the update operation
        """
        log.debug(
            "[actions]- [update-to-tls-v1.2-from-event] "
            "The resource:[apig-api-groups] processing event: %s", event)

        # Extract response from event
        response = jmespath.search('cts.response', event)
        if not response:
            log.warning(
                "[actions]- [update-to-tls-v1.2-from-event] "
                "The resource:[apig-api-groups] no cts.response found in event")
            return self.process_result([])

        # Parse response if it's a string
        if isinstance(response, str):
            try:
                response = json.loads(response)
            except json.JSONDecodeError as e:
                log.error(
                    "[actions]- [update-to-tls-v1.2-from-event] "
                    "The resource:[apig-api-groups] failed to parse "
                    "cts.response as JSON: %s", str(e))
                return self.process_result([])

        # Check if response is a dict
        if not isinstance(response, dict):
            log.error(
                "[actions]- [update-to-tls-v1.2-from-event] "
                "The resource:[apig-api-groups] cts.response is not a dict: %s",
                type(response))
            return self.process_result([])

        # Get domain ID from response (response.id is the domain_id)
        domain_id = response.get('id')
        if not domain_id:
            log.error(
                "[actions]- [update-to-tls-v1.2-from-event] "
                "The resource:[apig-api-groups] no domain ID found in response")
            return self.process_result([])

        # Get instance_id and group_id from event
        instance_id = jmespath.search('cts.resource_id', event)

        url_parts = jmespath.search('cts.message', event).split('/')
        group_id = url_parts[url_parts.index('api-groups') + 1]

        if not instance_id:
            log.error(
                "[actions]- [update-to-tls-v1.2-from-event] "
                "The resource:[apig-api-groups] no instance_id available")
            return self.process_result([])

        if not group_id:
            log.error(
                "[actions]- [update-to-tls-v1.2-from-event] "
                "The resource:[apig-api-groups] no group_id available")
            return self.process_result([])

        # Check current min_ssl_version
        min_ssl_version = response.get('min_ssl_version')
        domain_name = response.get('url_domain', domain_id)
        if min_ssl_version != 'TLSv1.1':
            log.info(
                "[actions]- [update-to-tls-v1.2-from-event] "
                "The resource:[apig-api-groups] with key:[%s/%s] "
                "min_ssl_version is %s, no update needed",
                domain_name, domain_id, min_ssl_version)
            return self.process_result([])

        log.info(
            "[actions]- [update-to-tls-v1.2-from-event] "
            "The resource:[apig-api-groups] with key:[%s/%s] "
            "updating min_ssl_version from %s to TLSv1.2",
            domain_name, domain_id, min_ssl_version)

        try:
            client = self.manager.get_client()

            # Query group details to check if it's the default group
            request = ShowDetailsOfApiGroupV2Request(
                instance_id=instance_id,
                group_id=group_id
            )
            group_response = client.show_details_of_api_group_v2(request)
            group_details = safe_json_parse(group_response)
            url_domains = group_details.get("url_domains")
            url_domain = {}
            for i in range(len(url_domains)):
                if url_domains[i].get("id") == domain_id:
                    url_domain = url_domains[i]
                    break

            from huaweicloudsdkapig.v2.model.url_domain_modify import UrlDomainModify

            # Build update body from url_domain, only including fields that UrlDomainModify accepts
            # Get all valid field names from UrlDomainModify.openapi_types
            valid_fields = set(UrlDomainModify.openapi_types.keys())

            update_info = {}
            # Only copy fields that are valid for UrlDomainModify
            for key, value in url_domain.items():
                if key in valid_fields:
                    update_info[key] = value

            # Override req_protocol to HTTPS
            update_info['min_ssl_version'] = 'TLSv1.2'

            # Build domain modify request body
            update_body = UrlDomainModify(**update_info)

            # Create update request
            request = UpdateDomainV2Request(
                instance_id=instance_id,
                group_id=group_id,
                domain_id=domain_id,
                body=update_body
            )

            log.info(
                "[actions]- [update-to-tls-v1.2-from-event] "
                "The resource:[apig-api-groups] update request: "
                "instance_id=%s, group_id=%s, domain_id=%s",
                instance_id, group_id, domain_id)

            # Send update request
            client.update_domain_v2(request)
            domain_name = response.get('url_domain', domain_id)
            log.info(
                "[actions]- [update-to-tls-v1.2-from-event] "
                "The resource:[apig-api-groups] with key:[%s/%s] "
                "update min_ssl_version to TLSv1.2 is success.",
                domain_name, domain_id)

            return self.process_result([{'id': domain_id, 'url_domain': domain_name}])

        except exceptions.ClientRequestException as e:
            domain_name = response.get('url_domain', domain_id)
            log.error(
                "[actions]- [update-to-tls-v1.2-from-event] "
                "The resource:[apig-api-groups] with key:[%s/%s] "
                "update domain is failed, cause: status_code[%s] request_id[%s] "
                "error_code[%s] error_msg[%s]",
                domain_name, domain_id, e.status_code, e.request_id,
                e.error_code, e.error_msg, exc_info=True)
            raise
        except Exception as e:
            domain_name = response.get('url_domain', domain_id)
            log.error(
                "[actions]- [update-to-tls-v1.2-from-event] "
                "The resource:[apig-api-groups] with key:[%s/%s] "
                "update domain is failed, cause: %s",
                domain_name, domain_id, str(e), exc_info=True)
            raise

    def perform_action(self, resource):
        """
        This method is required by HuaweiCloudBaseAction but not used in event-based actions

        :param resource: Resource (not used)
        """
        pass


# Update SLDomain Setting
@ApiGroupResource.action_registry.register('update-sl-domain-setting')
class UpdateSLDomainSettingAction(HuaweiCloudBaseAction):
    """Update SLDomain setting action for API Gateway groups

    This action allows updating the debug domain access settings for API Gateway groups,
    controlling whether debug domains can be accessed.

    :example:
    Define a policy to update SLDomain settings for an API Gateway group:

    .. code-block:: yaml

        policies:
          - name: apig-group-update-sl-domain-setting
            resource: huaweicloud.apig-api-groups
            filters:
              - type: value
                key: sl_domain_access_enabled
                value: true
            actions:
              - type: update-sl-domain-setting
                sl_domain_access_enabled: false
    """

    schema = type_schema(
        'update-sl-domain-setting',
        sl_domain_access_enabled={'type': 'boolean', 'required': True}
    )

    def perform_action(self, resource):
        client = self.manager.get_client()
        group_id = resource['id']
        instance_id = resource.get('instance_id')

        if not instance_id:
            group_name = resource.get('name', 'unknown')
            log.error(
                "[actions]- [update-sl-domain-setting] The resource:[apig-api-groups] "
                "with key:[%s/%s] update SL domain setting is failed, "
                "cause: No available instance found", group_name, group_id)
            return

        try:
            # Build domain access setting object from policy data
            domain_setting = SlDomainAccessSetting(
                sl_domain_access_enabled=self.data['sl_domain_access_enabled']
            )

            # Create update request
            request = UpdateSlDomainSettingV2Request(
                instance_id=instance_id,
                group_id=group_id,
                body=domain_setting
            )

            # Send request
            response = client.update_sl_domain_setting_v2(request)
            group_name = resource.get('name', group_id)
            access_status = "enabled" if self.data['sl_domain_access_enabled'] else "disabled"
            log.info(
                "[actions]- [update-sl-domain-setting] "
                "The resource:[apig-api-groups] with key:[%s/%s] "
                "update SL domain setting (debug domain access %s) is success.",
                group_name, group_id, access_status)
            return response
        except exceptions.ClientRequestException as e:
            group_name = resource.get('name', group_id)
            access_status = (
                "enable" if self.data.get('sl_domain_access_enabled', False)
                else "disable")
            log.error(
                "[actions]- [update-sl-domain-setting] The resource:[apig-api-groups] "
                "with key:[%s/%s] %s debug domain access is failed, cause: "
                "status_code[%s] request_id[%s] error_code[%s] error_msg[%s]",
                group_name, group_id, access_status,
                e.status_code, e.request_id, e.error_code, e.error_msg)
            raise


# Plugin Resource Management
@resources.register('apig-plugin')
class ApigPluginResource(QueryResourceManager):
    """
    Huawei Cloud API Gateway Plugin Resource Management
    """

    class resource_type(TypeInfo):
        service = 'apig-plugin'
        enum_spec = ('list_plugins', 'plugins', 'offset')
        id = 'plugin_id'
        name = 'plugin_name'
        filter_name = 'plugin_name'
        filter_type = 'scalar'
        taggable = False

    def get_instance_id(self):
        """
        Query and get API Gateway instance ID
        """
        session = local_session(self.session_factory)

        # If instance_id is specified in the policy, use it directly
        if hasattr(self, 'data') and isinstance(self.data, dict) and 'instance_id' in self.data:
            instance_id = self.data['instance_id']
            log.info(
                "The resource:[apig-plugin] using instance_id from policy "
                "configuration: %s", instance_id)
            return [instance_id]

        # Query APIG instance list
        try:
            # Use apig-instance service client
            client = session.client('apig-instance')
            instances_request = ListInstancesV2Request(limit=500)
            response = client.list_instances_v2(instances_request)

            if hasattr(response, 'instances') and response.instances:
                instance_ids = []
                for instance in response.instances:
                    instance_ids.append(instance.id)
                return instance_ids
        except Exception as e:
            log.error(
                "The resource:[apig-plugin] query APIG instance list is failed, "
                "cause: %s", str(e), exc_info=True)
            raise

        return []

    def get_resources(self, resource_ids):
        resources = self.get_policy_resources()
        result = []
        for resource in resources:
            if resource["plugin_id"] in resource_ids:
                resource["id"] = resource["plugin_id"]
                result.append(resource)
        return result

    def _fetch_resources(self, query):
        return self.get_policy_resources()

    def get_policy_resources(self):
        """Override resource retrieval method to query APIG plugins"""
        session = local_session(self.session_factory)
        client = session.client(self.resource_type.service)

        # Get instance ID
        instance_ids = self.get_instance_id()

        resources = []
        for instance_id in instance_ids:
            offset, limit = 0, 500
            while True:
                # Create new request object
                request = ListPluginsRequest(offset=offset, limit=limit)
                request.instance_id = instance_id

                # Call client method to process request
                try:
                    response = client.list_plugins(request)
                    resource = safe_json_parse(response.plugins)
                    for item in resource:
                        item["instance_id"] = instance_id
                    resources = resources + resource
                except exceptions.ClientRequestException as e:
                    log.error(
                        "The resource:[apig-plugin] query plugin list is failed, "
                        "cause: status_code[%s] request_id[%s] error_code[%s] "
                        "error_msg[%s]", e.status_code, e.request_id, e.error_code,
                        e.error_msg, exc_info=True)
                    raise

                offset += limit
                if not response.total or offset >= response.total:
                    break

        return resources


@ApigPluginResource.filter_registry.register('log-request-or-response-enable')
class LogRequestOrResponseEnableFilter(Filter):
    """Filter APIG plugins where any of the log request/response fields are enabled

    This filter checks if any of the following fields in the plugin's call_data are true:
    log_request_header, log_request_query_string, log_request_body, log_response_header,
    log_response_body.

    :example:

    .. code-block:: yaml

        policies:
          - name: apig-plugin-log-enable
            resource: huaweicloud.apig-plugin
            filters:
              - type: log-request-or-response-enable
    """

    schema = type_schema('log-request-or-response-enable')

    def process(self, resources, event=None):
        """
        Process resources to filter plugins where any log request/response fields are enabled

        :param resources: List of APIG plugin resources
        :param event: Optional event data
        :return: Filtered list of resources matching the criteria
        """
        matched_resources = []

        for resource in resources:
            plugin_content = resource.get('plugin_content')
            if not plugin_content:
                log.warning(
                    "[filters]- The filter:[log-request-or-response-enable] "
                    "query the service:[plugin_content] plugin content is empty or not found")
                continue

            try:
                # Parse plugin_content as JSON
                content_dict = json.loads(plugin_content)
                meta_config = content_dict.get('meta_config', {})
                call_data = meta_config.get('call_data', {})

                # Check each log field
                log_request_header = call_data.get('log_request_header', False)
                log_request_query_string = call_data.get('log_request_query_string', False)
                log_request_body = call_data.get('log_request_body', False)
                log_response_header = call_data.get('log_response_header', False)
                log_response_body = call_data.get('log_response_body', False)

                if (log_request_header or log_request_query_string or
                        log_request_body or log_response_header or log_response_body):
                    matched_resources.append(resource)
                    log.info(
                        "[filters]- The filter:[log-request-or-response-enable] "
                        "query the service:[plugin_content] plugin %s has log fields enabled",
                        resource.get('plugin_name', 'Unknown'))
            except Exception as e:
                log.error(
                    "[filters]- The filter:[log-request-or-response-enable] "
                    "query the service:[plugin_content] unexpected error while processing "
                    "plugin %s: %s",
                    resource.get('plugin_name', 'Unknown'), str(e), exc_info=True)
                raise

        return matched_resources
