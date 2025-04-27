# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
import json
import logging
import os
from datetime import datetime, timedelta
from typing import Optional, Tuple
import requests
from c7n.registry import PluginRegistry
from c7n.provider import Provider, clouds
from .apig_sdk import signer
from .client import Session

from .resources.resource_map import ResourceMap

log = logging.getLogger("custodian.huaweicloud.provider")

# Constants
ECS_AGENCY_CREDENTIAL_URL = "http://169.254.169.254/openstack/latest/securitykey"
CREDENTIAL_EXPIRY_BUFFER = timedelta(minutes=15)


class CredentialManager:
    def __init__(self):
        self.ecs_ak: Optional[str] = None
        self.ecs_sk: Optional[str] = None
        self.ecs_token: Optional[str] = None
        self.expiry_time: Optional[datetime] = None

    def get_valid_credentials(self) -> Tuple[str, str, str]:
        if self._credentials_expired():
            if not self._refresh_credentials():
                raise RuntimeError("Failed to obtain valid ECS agency credentials")
        return self.ecs_ak, self.ecs_sk, self.ecs_token

    def _credentials_expired(self) -> bool:
        return (
                not all([self.ecs_ak, self.ecs_sk, self.ecs_token]) or
                not self.expiry_time or
                datetime.now() + CREDENTIAL_EXPIRY_BUFFER >= self.expiry_time
        )

    def _refresh_credentials(self) -> bool:
        try:
            resp = requests.get(ECS_AGENCY_CREDENTIAL_URL, timeout=5)
            resp.raise_for_status()
            data = resp.json()

            if not data.get('credential'):
                log.error("No credential data in response")
                return False

            self.ecs_ak = data['credential']['access']
            self.ecs_sk = data['credential']['secret']
            self.ecs_token = data['credential']['securitytoken']
            self.expiry_time = datetime.now() + timedelta(hours=24)
            return True

        except requests.exceptions.RequestException as e:
            log.error(f"Request for ECS credentials failed: {str(e)}")
        except (KeyError, ValueError) as e:
            log.error(f"Invalid credential response format: {str(e)}")
        except Exception as e:
            log.error(f"Unexpected error refreshing credentials: {str(e)}")

        return False


class HuaweiSessionFactory:

    def __init__(self, options):
        self.options = options
        self.credential_manager = CredentialManager()
        self._validate_credentials_config()

    def _validate_credentials_config(self):
        self.use_assume = hasattr(self.options, 'agency_urn') and self.options.agency_urn
        self.ak = getattr(self.options, 'access_key_id', os.getenv('HUAWEI_ACCESS_KEY_ID'))
        self.sk = getattr(self.options, 'secret_access_key', os.getenv('HUAWEI_SECRET_ACCESS_KEY'))
        self.token = getattr(self.options, 'security_token', os.getenv('HUAWEI_SECURITY_TOKEN'))

        if not self.use_assume and not (self.ak and self.sk):
            raise ValueError(
                "Either agency_urn (for assume role) or "
                "access_key_id/secret_access_key must be configured"
            )

    def __call__(self, assume=True, region=None):
        (self.options['access_key_id'],
         self.options['secret_access_key'],
         self.options['security_token']) = self.get_credential()
        return Session(self.options)

    def get_credential(self):
        if self.use_assume:
            log.info("get v5 assume credential.")
            return self._get_assumed_credentials()
        log.info("Using direct AK/SK credentials")
        return self.ak, self.sk, self.token

    def _get_assumed_credentials(self):
        try:
            ecs_ak, ecs_sk, ecs_token = self.credential_manager.get_valid_credentials()
            sig = signer.Signer()
            sig.Key = ecs_ak
            sig.Secret = ecs_sk
            url = f"https://sts.{self.options.region}.myhuaweicloud.com/v5/agencies/assume"
            request = signer.HttpRequest("POST", url)
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
