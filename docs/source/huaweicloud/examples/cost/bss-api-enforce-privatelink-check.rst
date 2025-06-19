COST - CHECK VPCIDS
========================

.. code-block:: yaml

  policies:
    - name: bss-api-enforce-privatelink-check
      description: |
        Check whether the Huawei Cloud account used by the customer for cloud cost and billing management has created a VPC endpoint resource for calling the customer's Operation capability OpenAPI, and whether the VPC where the VCPEP endpoint is located meets the design expectations (it is indeed necessary to initiate API calls from this VPC).
      resource: huaweicloud.vpcep-ep
      mode:
        type: huaweicloud-periodic
        xrole: fgs_admin
        enable_lts_log: true
        log_level: INFO
        func_vpc:
          vpc_id: xxx
          subnet_id: xxx
        schedule: "1h"
        schedule_type: Rate
      filters:
        - type: value
          key: endpoint_service_name
          value: "bss-intl.myhuaweicloud.com"
        - type: value
          key: vpc_id
          op: in
          value:
            - xxxx
            - xxxx
            - xxxx
      actions:
        - type: eps-check-ep-msg
          topic_urn_list:
            - "urn:smn:ap-southeast-1:ff197a18dc324b6f93e20d5bde1aab34:eps-check-ep-cost"
          message: "The security baseline 'HW-COST-CENTER-003' has risks. The VPCEP configuration for calling the Huawei Cloud Customer Operation Capacity OpenAPI from the VPC where the customer system is located does not match the expected configuration."


