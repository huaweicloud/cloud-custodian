# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import json
import logging
import os
import requests
from huaweicloudsdkcore.auth.credentials import Credentials
from huaweicloudsdkcore.utils import time_utils

from c7n.registry import PluginRegistry
from c7n.provider import Provider, clouds
from c7n_huaweicloud.client import Session

from c7n_huaweicloud.resources.resource_map import ResourceMap
from c7n_huaweicloud.utils.signer import Signer, HttpRequest

log = logging.getLogger("custodian.huaweicloud.provider")

credential = Credentials()


def get_credentials():
    if (not credential.security_token or
            credential._expired_at - time_utils.get_timestamp_utc() < 60):
        credential.update_security_token_from_metadata()
    return credential.ak, credential.sk, credential.security_token


class HuaweiSessionFactory:

    def __init__(self, options):
        self.options = options
        self._validate_credentials_config()

    def _validate_credentials_config(self):
        self.use_assume = hasattr(self.options, 'agency_urn') and self.options.agency_urn
        self.ak = getattr(self.options, 'access_key_id', os.getenv('HUAWEI_ACCESS_KEY_ID'))
        self.sk = getattr(self.options, 'secret_access_key', os.getenv('HUAWEI_SECRET_ACCESS_KEY'))
        self.token = getattr(self.options, 'security_token', os.getenv('HUAWEI_SECURITY_TOKEN'))

    def __call__(self):
        (self.options['access_key_id'],
         self.options['secret_access_key'],
         self.options['security_token']) = self.get_credential()

        return Session(self.options)

    def get_credential(self):
        if self.use_assume:
            log.info("get v5 assume credential.")
            return self._get_assumed_credentials()
        return self.ak, self.sk, self.token

    def _get_assumed_credentials(self):
        try:
            ecs_ak, ecs_sk, ecs_token = get_credentials()
            sig = Signer()
            sig.Key = ecs_ak
            sig.Secret = ecs_sk
            url = f"https://sts.{self.options.region}.myhuaweicloud.com/v5/agencies/assume"
            request = HttpRequest("POST", url)
            request.headers = {"Content-Type": "application/json", "X-Security-Token": ecs_token}
            request.body = json.dumps({
                "duration_seconds": getattr(self.options, 'duration_seconds', 3600),
                "agency_urn": self.options.agency_urn,
                "agency_session_name": "custodian_agency_session",
            })
            sig.Sign(request)
            resp = requests.post(url, headers=request.headers, data=request.body)
            resp.raise_for_status()
            json_resp = resp.json()
            if not json_resp.get("credentials"):
                raise ValueError("No credentials in assume role response")
            creds = json_resp["credentials"]
            return creds["access_key_id"], creds["secret_access_key"], creds["security_token"]

        except requests.exceptions.HTTPError as e:
            log.error(f"Assume role request failed with status:{e.response.status_code}, "
                      f"exception: {str(e)}")
            raise ValueError(f"Assume role failed: {str(e)}")
        except (KeyError, ValueError) as e:
            log.error(f"Invalid assume role response: {str(e)}")
            raise ValueError("Invalid assume role response format")
        except Exception as e:
            log.error(f"Unexpected error during assume role: {str(e)}")
            raise


@clouds.register("huaweicloud")
class HuaweiCloud(Provider):
    display_name = "Huawei Cloud"
    resource_prefix = "huaweicloud"
    resources = PluginRegistry("%s.resources" % resource_prefix)
    resource_map = ResourceMap

    def initialize(self, options):
        return options

    def initialize_policies(self, policy_collection, options):
        return policy_collection

    def get_session_factory(self, options):
        return HuaweiSessionFactory(options)


resources = HuaweiCloud.resources
