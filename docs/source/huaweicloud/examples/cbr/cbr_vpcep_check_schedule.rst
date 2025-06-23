policies:
  - name: cbr_vpcep_check_schedule
    resource: huaweicloud.vpcep-ep
    mode:
      type: huaweicloud-periodic
      xrole: fgs_admin
      eg_agency: EG_TARGET_AGENCY
      enable_lts_log: true
      schedule: "1h"
      schedule_type: Rate
    filters:
      - type: by-service-and-vpc-check
        endpoint_service_name: "com.myhuaweicloud.xxxxxxx.cbr"
    actions:
      - type: eps-check-ep-msg
        topic_urn_list:
          - "urn:smn:xxxx:xxxxx:custodian_test"
        message: "Alert: please check whether the vpc endpoint for cbr has been created."