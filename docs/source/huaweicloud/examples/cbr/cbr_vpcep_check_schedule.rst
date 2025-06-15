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
        endpoint_service_name: "com.myhuaweicloud.sa-brazil-1.cbr"
    actions:
      - type: eps-check-ep-msg
        topic_urn_list:
          - "urn:smn:sa-brazil-1:0d8df128318091f52ff1c0069c340775:custodian_test"
        message: "Alert: please check whether the vpc endpoint for cbr has been created."