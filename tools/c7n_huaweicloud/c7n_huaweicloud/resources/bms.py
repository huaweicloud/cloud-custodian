# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

import logging
import base64
import json
import zlib
from concurrent.futures import as_completed

from huaweicloudsdkcore.exceptions import exceptions
from huaweicloudsdkbms.v1 import (
    ListBareMetalServerDetailsRequest,
    BatchStartBaremetalServersRequest,
    BatchStopBaremetalServersRequest,
    BatchRebootBaremetalServersRequest,
    OsStartBody,
    OsStopBody,
    OsStopBodyType,
    RebootBody,
    UpdateBaremetalServerMetadataRequest,
    UpdateBaremetalServerMetadataReq,
    StartServersInfo, ServersList, ServersInfoType,
    ShowBaremetalServerVolumeInfoRequest,
)

from huaweicloudsdkims.v2 import (
    ListImagesRequest,
)


from c7n import utils
from c7n.utils import type_schema, local_session
from c7n_huaweicloud.actions.base import HuaweiCloudBaseAction
from c7n_huaweicloud.provider import resources
from c7n_huaweicloud.query import QueryResourceManager, TypeInfo
from c7n.filters import AgeFilter, ValueFilter, Filter
from dateutil.parser import parse

log = logging.getLogger("custodian.huaweicloud.resources.bms")


@resources.register("bms")
class Bms(QueryResourceManager):
    """Huawei Cloud Bare Metal Server Resources"""
    class resource_type(TypeInfo):
        service = "bms"
        enum_spec = ("list_bare_metal_servers", "servers", "page")
        id = "id"
        tag_resource_type = "bms_server"

    def augment(self, resources):
        if not resources:
            return resources
        for resource in resources:
            if "tags" in resource and isinstance(resource["tags"], list):
                if "__type_baremetal" in resource["tags"]:
                    index = resource["tags"].index("__type_baremetal")
                    del resource["tags"][index]
        return resources
# ----------------------- BMS Filters -----------------------


@Bms.filter_registry.register("instance-age")
class BmsInstanceAgeFilter(AgeFilter):
    """BMS instance with creation time filter: greater than or less than a specified threshold date

    :Example:

    .. code-block:: yaml

        policies:
          - name: bms-instances-age
            resource: huaweicloud.bms
            filters:
              - type: instance-age
                op: le
                days: 30
    """

    date_attribute = "created"

    schema = type_schema(
        "instance-age",
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number"},
        hours={"type": "number"},
        minutes={"type": "number"},
    )


@Bms.filter_registry.register("instance-uptime")
class BmsInstanceUptimeFilter(AgeFilter):
    """Filter BMS instances with uptime greater than or less than a given uptime.

    :Example:

    .. code-block:: yaml

        policies:
          - name: bms-instances-long-running
            resource: huaweicloud.bms
            filters:
              - type: instance-uptime
                op: ge
                days: 90
    """

    date_attribute = "created"

    schema = type_schema(
        "instance-uptime",
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number"},
    )


@Bms.filter_registry.register("instance-attribute")
class BmsInstanceAttributeFilter(ValueFilter):
    """BMS instance with attribute value filter.

    :Example:

    .. code-block:: yaml

        policies:
          - name: bms-instances-attribute
            resource: huaweicloud.bms
            filters:
              - type: instance-attribute
                attribute: OS-EXT-SRV-ATTR:root_device_name
                key: "Value"
                op: eq
                value: /dev/sda
    """

    valid_attrs = (
        "flavorId",
        "OS-EXT-SRV-ATTR:user_data",
        "OS-EXT-SRV-ATTR:root_device_name",
    )

    schema = type_schema(
        "instance-attribute",
        rinherit=ValueFilter.schema,
        attribute={"enum": valid_attrs},
        required=("attribute",),
    )
    schema_alias = False

    def process(self, resources, event=None):
        attribute = self.data["attribute"]
        self.get_instance_attribute(resources, attribute)
        return [
            resource
            for resource in resources
            if self.match(resource["c7n:attribute-%s" % attribute])
        ]

    def get_instance_attribute(self, resources, attribute):
        for resource in resources:
            userData = resource.get("OS-EXT-SRV-ATTR:user_data", "")
            flavorId = resource["flavor"]["id"]
            rootDeviceName = resource.get("OS-EXT-SRV-ATTR:root_device_name", "")
            attributes = {
                "OS-EXT-SRV-ATTR:user_data": {"Value": deserialize_user_data(userData)},
                "flavorId": {"Value": flavorId},
                "OS-EXT-SRV-ATTR:root_device_name": {"Value": rootDeviceName},
            }
            resource["c7n:attribute-%s" % attribute] = attributes[attribute]


class BmsInstanceImageBase:
    """BMS instance with image base class"""

    def prefetch_instance_images(self, instances):
        self.image_map = self.get_local_image_mapping(instances)

    def get_base_image_mapping(self, image_ids):
        ims_client = local_session(self.manager.session_factory).client("ims")
        request = ListImagesRequest(id=image_ids, limit=1000)
        return {i.id: i for i in ims_client.list_images(request).images}

    def get_instance_image_created_at(self, instance):
        return instance["image:created_at"]

    def get_local_image_mapping(self, instances):
        image_ids = ",".join(
            list(set(item["metadata"]["metering.image_id"] for item in instances))
        )
        base_image_map = self.get_base_image_mapping(image_ids)
        for r in instances:
            if r["metadata"]["metering.image_id"] in base_image_map.keys():
                r["image:created_at"] = base_image_map[
                    r["metadata"]["metering.image_id"]
                ].created_at
            else:
                r["image:created_at"] = "2000-01-01T01:01:01.000Z"
        return instances


@Bms.filter_registry.register("instance-image-age")
class BmsImageAgeFilter(AgeFilter, BmsInstanceImageBase):
    """BMS instance with image age filter

    Filter BMS instances based on the creation time of the image

    :Example:

    .. code-block:: yaml

        policies:
          - name: bms-old-image
            resource: huaweicloud.bms
            filters:
              - type: instance-image-age
                op: ge
                days: 180
    """

    date_attribute = "created_at"

    schema = type_schema(
        "instance-image-age",
        op={"$ref": "#/definitions/filters_common/comparison_operators"},
        days={"type": "number"},
    )

    def process(self, resources, event=None):
        self.prefetch_instance_images(resources)
        return super(BmsImageAgeFilter, self).process(resources, event)

    def get_resource_date(self, i):
        image = self.get_instance_image_created_at(i)
        return parse(image)


@Bms.filter_registry.register("instance-image")
class BmsInstanceImageFilter(ValueFilter, BmsInstanceImageBase):
    """BMS instance with image filter

    :Example:

    .. code-block:: yaml

        policies:
          - name: bms-image-filter
            resource: huaweicloud.bms
            filters:
              - type: instance-image
    """

    schema = type_schema("instance-image", rinherit=ValueFilter.schema)
    schema_alias = False

    def process(self, resources, event=None):
        results = []
        image_ids = ",".join(
            list(item["metadata"]["metering.image_id"] for item in resources)
        )
        base_image_map = self.get_base_image_mapping(image_ids)
        for r in resources:
            if r["metadata"]["metering.image_id"] in base_image_map.keys():
                results.append(r)
        return results


def deserialize_user_data(user_data):
    """Parse user data content"""
    if not user_data:
        return ""
    data = base64.b64decode(user_data)
    # Try decoding both plain and compressed formats
    try:
        return data.decode("utf8")
    except UnicodeDecodeError:
        return zlib.decompress(data, 16).decode("utf8")


@Bms.filter_registry.register("instance-user-data")
class BmsInstanceUserData(ValueFilter):
    """Filter BMS instances with matching user data

    Note: It is recommended to use regular expressions,
    as Custodian uses re.match() and the user data may span multiple lines.

    :example:

    .. code-block:: yaml

        policies:
          - name: bms-instance-user-data
            resource: huaweicloud.bms
            filters:
              - type: instance-user-data
                op: regex
                value: (?smi).*user=
    """

    schema = type_schema("instance-user-data", rinherit=ValueFilter.schema)
    schema_alias = False
    batch_size = 50
    annotation = "OS-EXT-SRV-ATTR:user_data"

    def __init__(self, data, manager):
        super(BmsInstanceUserData, self).__init__(data, manager)
        self.data["key"] = "OS-EXT-SRV-ATTR:user_data"

    def process(self, resources, event=None):
        results = []
        with self.executor_factory(max_workers=3) as w:
            futures = {}
            for instance_set in utils.chunks(resources, self.batch_size):
                futures[w.submit(self.process_instance_user_data, instance_set)] = (
                    instance_set
                )

            for f in as_completed(futures):
                if f.exception():
                    self.log.error("Error occurred while process bms user data %s", f.exception()
                    )
                results.extend(f.result())
        return results

    def process_instance_user_data(self, resources):
        results = []
        client = self.manager.get_client()
        for r in resources:
            try:
                request = ListBareMetalServerDetailsRequest(server_id=r["id"])
                response = client.list_bare_metal_server_details(request)
                user_data = response.server.os_ext_srv_att_ruser_data
                r[self.annotation] = deserialize_user_data(user_data) if user_data else None
            except exceptions.ClientRequestException as e:
                log.error(e.status_code, e.request_id, e.error_code, e.error_msg)
                continue

            if self.match(r):
                results.append(r)
        return results


@Bms.filter_registry.register("ephemeral")
class BmsInstanceEphemeralFilter(Filter):
    """BMS instance with ephemeral storage

    Filter BMS instances with ephemeral storage

    :Example:

    .. code-block:: yaml

        policies:
          - name: bms-ephemeral
            resource: huaweicloud.bms
            filters:
              - type: ephemeral

    """

    schema = type_schema("ephemeral")

    def __call__(self, i):
        return self.is_ephemeral(i)

    def is_ephemeral(self, i):
        """BMS does not support ephemeral storage"""
        return False


@Bms.filter_registry.register("instance-vpc")
class BmsInstanceVpc(ValueFilter):
    """BMS instance with VPC filter


    :Example:

    .. code-block:: yaml

       policies:
         - name: bms-vpc-filter
           resource: huaweicloud.bms
           filters:
             - type: instance-vpc
    """

    schema = type_schema("instance-vpc")
    schema_alias = False

    def process(self, resources, event=None):
        return self.get_vpcs(resources)

    def get_vpcs(self, resources):
        vpcs = self.manager.get_resource_manager("huaweicloud.vpc").resources()
        vpc_ids = {vpc["id"] for vpc in vpcs}
        return [
            resource for resource in resources
            if resource["metadata"]["vpc_id"] in vpc_ids
        ]


@Bms.filter_registry.register("instance-evs")
class BmsInstanceEvs(ValueFilter):
    """BMS instance with EVS volume。

    Filter BMS instances with EVS storage devices

    :Example:

    .. code-block:: yaml

       policies:
         - name: bms-instance-evs
           resource: huaweicloud.bms
           filters:
             - type: instance-evs
               key: id
               op: eq
               value: "volume ID"
    """

    schema = type_schema(
        "instance-evs",
        rinherit=ValueFilter.schema,
        **{"skip-devices": {"type": "array", "items": {"type": "string"}}}
    )
    schema_alias = False
    batch_size = 10

    def process(self, resources, event=None):
        self.skip = self.data.get("skip-devices", [])
        self.operator = self.data.get("operator", "or") == "or" and any or all
        results = []
        with self.executor_factory(max_workers=3) as w:
            futures = {}
            for instance_set in utils.chunks(resources, self.batch_size):
                futures[w.submit(self.process_instance_volumes, instance_set)] = instance_set

            for f in as_completed(futures):
                if f.exception():
                    self.log.error(
                        "Error occurred while process bms volume information %s", f.exception())
                results.extend(f.result())
        return results

    def process_instance_volumes(self, resources):
        client = self.manager.get_client()
        results = []
        for r in resources:
            try:
                request = ShowBaremetalServerVolumeInfoRequest(server_id=r["id"])
                response = client.show_baremetal_server_volume_info(request)
                volumes = response.volume_attachments

                if not volumes:
                    continue

                if self.skip:
                    volumes = [v for v in volumes if v.device not in self.skip]

                if not volumes:
                    continue

                r['c7n:volumes'] = [v.to_dict() for v in volumes]

                if r['c7n:volumes']:
                    for volume in r['c7n:volumes']:
                        if self.match(volume):
                            results.append(r)
            except exceptions.ClientRequestException as e:
                log.error(f"{e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
                continue
        return results

    def __call__(self, r):
        volumes = r.get('c7n:volumes', [])
        if not volumes:
            return False
        return self.match(volumes)


# ----------------------- BMS Actions -----------------------

@Bms.action_registry.register("fetch-job-status")
class BmsFetchJobStatus(HuaweiCloudBaseAction):
    """Fetch An Asyn Job Status.

    :Example:

    .. code-block:: yaml

        policies:
          - name: bms-fetch-job-status
            resource: huaweicloud.bms
            actions:
              - type: fetch-job-status
                job_id: "Async Job ID"
    """

    schema = type_schema(
        "fetch-job-status", job_id={"type": "string"}, required=("job_id",)
    )

    def process(self, resources):
        job_id = self.data.get("job_id")
        client = self.manager.get_client()
        from huaweicloudsdkbms.v1 import ShowJobInfosRequest
        request = ShowJobInfosRequest(job_id=job_id)
        try:
            response = client.show_job_infos(request)
        except exceptions.ClientRequestException as e:
            log.error(f"{e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise
        return json.dumps(response.to_dict())

    def perform_action(self, resource):
        return super().perform_action(resource)


@Bms.action_registry.register("instance-start")
class BmsStart(HuaweiCloudBaseAction):
    """Start Bare Metal Server.

    :Example:

    .. code-block:: yaml

        policies:
          - name: start-bms-server
            resource: huaweicloud.bms
            filters:
              - type: value
                key: id
                value: "BMS server ID"
            actions:
              - instance-start
    """

    valid_origin_states = ("SHUTOFF",)
    schema = type_schema("instance-start")

    def process(self, resources):
        if len(resources) > 1000:
            log.error("The most bare metal instances to start is 1000")
            return

        client = self.manager.get_client()
        instances = self.filter_resources(resources, "status", self.valid_origin_states)

        if not instances:
            log.warning("No bare metal instances to start")
            return None

        request = self.init_request(instances)
        try:
            response = client.batch_start_baremetal_servers(request)
        except exceptions.ClientRequestException as e:
            log.error(f"{e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise
        return json.dumps(response.to_dict())

    def init_request(self, instances):
        server_ids = []
        for r in instances:
            server_ids.append(ServersList(r["id"]))

        server_info = StartServersInfo(servers=server_ids)
        os_start = OsStartBody(os_start=server_info)
        request = BatchStartBaremetalServersRequest(body=os_start)
        return request

    def perform_action(self, resource):
        return super().perform_action(resource)


@Bms.action_registry.register("instance-stop")
class BmsStop(HuaweiCloudBaseAction):
    """Stop Bare Metal Server.

    :Example:

    .. code-block:: yaml

        policies:
          - name: stop-bms-server
            resource: huaweicloud.bms
            filters:
              - type: value
                key: id
                value: "BMS server ID"
            actions:
              - type: instance-stop
                mode: "SOFT"
    """

    valid_origin_states = ("ACTIVE",)
    schema = type_schema("instance-stop", mode={"type": "string"})

    def process(self, resources):
        if len(resources) > 1000:
            log.error("The most bare metal instances to stop is 1000")
            return

        client = self.manager.get_client()
        instances = self.filter_resources(resources, "status", self.valid_origin_states)

        if not instances:
            log.warning("No bare metal instances to stop")
            return None

        request = self.init_request(instances)
        try:
            response = client.batch_stop_baremetal_servers(request)
        except exceptions.ClientRequestException as e:
            log.error(f"{e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise
        return json.dumps(response.to_dict())

    def init_request(self, instances):
        server_ids = []
        for r in instances:
            server_ids.append(ServersList(r["id"]))
        mode = self.data.get("mode", "SOFT")
        os_stop = OsStopBodyType(type=mode, servers=server_ids)
        body = OsStopBody(os_stop=os_stop)
        request = BatchStopBaremetalServersRequest(body=body)
        return request

    def perform_action(self, resource):
        return super().perform_action(resource)


@Bms.action_registry.register("instance-reboot")
class BmsReboot(HuaweiCloudBaseAction):
    """Reboot Bare Metal Server.

    :Example:

    .. code-block:: yaml

        policies:
          - name: reboot-bms-server
            resource: huaweicloud.bms
            filters:
              - type: value
                key: id
                value: "BMS server ID"
            actions:
              - type: instance-reboot
                mode: "SOFT"
    """

    valid_origin_states = ("ACTIVE",)
    schema = type_schema("instance-reboot", mode={"type": "string"})

    def process(self, resources):
        if len(resources) > 1000:
            log.error("The most bare metal instances to reboot is 1000")
            return
        client = self.manager.get_client()
        instances = self.filter_resources(resources, "status", self.valid_origin_states)
        if not instances:
            log.warning("No bare metal instances to reboot")
            return None
        request = self.init_request(instances)
        try:
            response = client.batch_reboot_baremetal_servers(request)
        except exceptions.ClientRequestException as e:
            log.error(f"{e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise
        return json.dumps(response.to_dict())

    def init_request(self, instances):
        server_ids = []
        for r in instances:
            server_ids.append(ServersList(r["id"]))

        mode = self.data.get("mode", "SOFT")
        os_reboot = ServersInfoType(type=mode, servers=server_ids)
        reboot = RebootBody(reboot=os_reboot)
        request = BatchRebootBaremetalServersRequest(body=reboot)
        return request

    def perform_action(self, resource):
        return super().perform_action(resource)


@Bms.action_registry.register("set-instance-profile")
class BmsSetInstanceProfile(HuaweiCloudBaseAction):
    """Set The Metadata Of Bare Metal Server.

    :Example:

    .. code-block:: yaml

        policies:
          - name: set-bms-profile
            resource: huaweicloud.bms
            filters:
              - type: value
                key: id
                value: "BMS server ID"
            actions:
              - type: set-instance-profile
                metadata:
                  key1: value1
                  key2: value2
    """

    schema = type_schema("set-instance-profile", metadata={"type": "object"})

    def perform_action(self, resource):
        client = self.manager.get_client()
        metadata = self.data.get("metadata", None)
        if not metadata:
            log.warning("No metadata provided")
            return None

        metadata_req = UpdateBaremetalServerMetadataReq(metadata=metadata)
        request = UpdateBaremetalServerMetadataRequest(
            server_id=resource["id"], body=metadata_req
        )
        try:
            response = client.update_baremetal_server_metadata(request)
            return response
        except exceptions.ClientRequestException as e:
            log.error(f"{e.status_code}, {e.request_id}, {e.error_code}, {e.error_msg}")
            raise
