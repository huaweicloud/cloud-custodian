# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager
from c7n_huaweicloud.query import TypeInfo
# Centralized imports for HuaweiCloud SDK modules
from huaweicloudsdkcodeartsbuild.v3 import ShowJobConfigRequest

from c7n.filters import Filter
from c7n.utils import local_session, type_schema

log = logging.getLogger('custodian.huaweicloud.codearts-build')


@resources.register('codearts-build-job')
class Job(QueryResourceManager):
    """
    CodeArtsBuild JOB Manager.
    """

    class resource_type(TypeInfo):
        service = 'codearts-build'
        enum_spec = ('list_job', 'result.job_list', "page_index")
        page_size = 100
        id = 'id'  # Specify resource unique identifier field name
        tag_resource_type = None

    def get_resources(self, resource_ids):
        resources = (self.augment(self.source.get_resources(self.get_resource_query())) or [])
        resource_map = {r["id"]: r for r in resources if "id" in r}
        result = []

        for resource_id in resource_ids:
            if resource_id in resource_map:
                resource = resource_map[resource_id]
                resource["exist"] = True
                result.append(resource)
            else:
                not_exist_resource = {
                    "id": resource_id,
                    "exist": False
                }
                result.append(not_exist_resource)
        return result


@Job.filter_registry.register('not-exist')
class NotExistFilter(Filter):
    """ codearts build execution-host filter.

    Filters the job to find those not exist in project

    :example:

     .. code-block:: yaml

       policies:
        - name: execution-host
          resource: huaweicloud.codearts-build-job
          filters:
            - type: not-exist
     """
    schema = type_schema('exist')

    def process(self, resources, event=None):
        result = []
        for resource in resources:
            if not resource.get("exist", True):
                result.append(resource)
        return result


@Job.filter_registry.register('execution-host')
class ExecutionHostFilter(Filter):
    """ codearts build execution-host filter.

    Filters an build execution-host based on name and id

    :example:

     .. code-block:: yaml

       policies:
        - name: execution-host
          resource: huaweicloud.codearts-build-job
          filters:
            - type: execution-host
              host_type: default
              id: c7a85a3f43174298a6ceb970e7e41e55
     """
    schema = type_schema(
        "execution-host",
        host_type={'type': 'string', 'enum': ['default', 'exclusive', 'custom']},
        id={'type': 'string'})

    def process(self, resources, event=None):
        results = []
        client = local_session(self.manager.session_factory).client('codearts-build')
        job_id = self.data.get('id')
        expected_type = self.data.get('host_type')

        if not expected_type:
            self.log.warning("Expected type is required but not provided")
            return results

        try:
            if not job_id:
                self._process_all_resources(client, resources, expected_type, results)
            else:
                self._process_single_resource(client, resources, job_id, expected_type, results)

        except Exception as e:
            self.log.error(f"Error processing job(s): {str(e)}")

        return results

    def _show_job_config(self, client, job_id):
        # 参数验证
        if not job_id:
            self.log.error("Job ID cannot be None or empty")
            raise ValueError("Job ID is required")

        if not client:
            self.log.error("Client cannot be None")
            raise ValueError("Client is required")

        try:
            request = ShowJobConfigRequest()
            request.job_id = job_id

            response = client.show_job_config(request)

            if not response or not hasattr(response, 'result'):
                self.log.warning(f"Empty or invalid response for job {job_id}")
                return None

            return response.result

        except AttributeError as e:
            self.log.error(f"Invalid client object or missing show_job_config method: {e}")

        except Exception as e:
            self.log.error(f"Failed to get job config for {job_id}: {e}")
            return None

    def determine_type(self, config):
        host_type = getattr(config, 'host_type', None)
        cluster_selected = getattr(config, 'cluster_selected', None)

        cluster_resource_type = None
        if cluster_selected is not None:
            cluster_resource_type = getattr(cluster_selected, 'resource_type', None)

        if host_type == 'devcloud':
            return 'default'
        elif host_type == 'custom_host':
            if cluster_resource_type == 'exclusive':
                return 'exclusive'
            elif cluster_resource_type == 'self-hosted':
                return 'custom'
        return 'unknown'

    def _process_single_resource(self, client, resources, job_id, expected_type, results):
        target_resource = None
        for resource in resources:
            if not resource.get("exist", True):
                continue
            if resource['id'] == job_id:
                target_resource = resource
                break

        if not target_resource:
            self.log.warning(f"Job with ID {job_id} not found in resources")
            return

        job_config = self._show_job_config(client, job_id)
        if not job_config:
            self.log.warning(f"Failed to get configuration for job {job_id}")
            return

        actual_type = self.determine_type(job_config)
        if actual_type == expected_type:
            results.append(target_resource)
        else:
            self.log.debug(f"Job {job_id} type mismatch: expected {expected_type}"
                           f", got {actual_type}")

    def _process_all_resources(self, client, resources, expected_type, results):
        for resource in resources:
            if not resource.get("exist", True):
                continue
            resource_id = resource['id']
            try:
                job_config = self._show_job_config(client, resource_id)
                if not job_config:
                    self.log.warning(f"Failed to get configuration for job {resource_id}")
                    continue

                actual_type = self.determine_type(job_config)
                if actual_type == expected_type:
                    results.append(resource)
                    self.log.debug(f"Job {resource_id} matched expected type {expected_type}")
                else:
                    self.log.debug(f"Job {resource_id} type mismatch: expected {expected_type}"
                                   f", got {actual_type}")

            except Exception as e:
                self.log.error(f"Error processing job {resource_id}: {str(e)}")
