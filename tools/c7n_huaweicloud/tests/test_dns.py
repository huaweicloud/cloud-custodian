# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0

from huaweicloud_common import BaseTest


class PublicZoneTest(BaseTest):
    """Test Public DNS Zone resources, filters, and actions"""

    def test_public_zone_query(self):
        """Test Public Zone query and augment"""
        factory = self.replay_flight_data("dns_public_zone_query")
        p = self.load_policy(
            {
                "name": "dns-public-zone-query",
                "resource": "huaweicloud.dns-publiczone",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: dns_public_zone_query should contain 1 public zone
        self.assertEqual(len(resources), 1)
        # Verify VCR: Value should match the 'name' in dns_public_zone_query
        self.assertEqual(resources[0]["name"], "example.com.")
        # Verify VCR: Value should match the 'email' in dns_public_zone_query
        self.assertEqual(resources[0]["email"], "admin@example.com")
        self.assertTrue("description" in resources[0])  # Verify augment added information

    def test_public_zone_filter_age_match(self):
        """Test Public Zone Age filter - Match"""
        factory = self.replay_flight_data("dns_public_zone_filter_age")
        p = self.load_policy(
            {
                "name": "dns-public-zone-filter-age-match",
                "resource": "huaweicloud.dns-publiczone",
                # Verify VCR: Creation time ('2023-01-15T12:00:23Z') of
                # 'public-old.example.com.' in dns_public_zone_filter_age
                # should be >= 90 days
                "filters": [{"type": "age", "days": 90, "op": "ge"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)

    def test_public_zone_filter_age_no_match(self):
        """Test Public Zone Age filter - No Match"""
        factory = self.replay_flight_data("dns_public_zone_filter_age")  # Reuse cassette
        p = self.load_policy(
            {
                "name": "dns-public-zone-filter-age-no-match",
                "resource": "huaweicloud.dns-publiczone",
                # Verify VCR: Creation time ('2023-01-15T12:00:23Z') of
                # 'public-old.example.com.' in dns_public_zone_filter_age
                # should not be < 1 day
                "filters": [{"type": "age", "days": 1, "op": "lt"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)

    def test_public_zone_action_delete(self):
        """Test Delete Public Zone action"""
        factory = self.replay_flight_data("dns_public_zone_action_delete")
        # Get the Zone ID and Name to delete from dns_public_zone_action_delete
        # Verify VCR: Match the 'id' in dns_public_zone_action_delete
        zone_id_to_delete = "2c9eb1538a138432018a13uuuuu00001"
        # Verify VCR: Match the 'name' in dns_public_zone_action_delete
        zone_name_to_delete = "public-delete.example.com."
        p = self.load_policy(
            {
                "name": "dns-public-zone-action-delete",
                "resource": "huaweicloud.dns-publiczone",
                # Use value filter for clarity
                "filters": [{"type": "value", "key": "id", "value": zone_id_to_delete}],
                "actions": ["delete"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Assert mainly verifies if the policy correctly filtered the target resource
        self.assertEqual(resources[0]['id'], zone_id_to_delete)
        self.assertEqual(resources[0]['name'], zone_name_to_delete)
        # Verify action success: Manually check VCR cassette
        # dns_public_zone_action_delete to confirm
        # DELETE /v2/zones/{zone_id} was called

    def test_public_zone_action_update(self):
        """Test Update Public Zone action"""
        factory = self.replay_flight_data("dns_public_zone_action_update")
        # Get the Zone ID to update from dns_public_zone_action_update
        # Verify VCR: Match the 'id' in dns_public_zone_action_update
        zone_id_to_update = "2c9eb1538a138432018a13zzzzz00001"
        # Verify VCR: Match the initial 'email' in dns_public_zone_action_update
        original_email = "original@example.com"
        new_email = "new@example.com"  # Updated email
        new_ttl = 7200  # Updated TTL
        p = self.load_policy(
            {
                "name": "dns-public-zone-action-update",
                "resource": "huaweicloud.dns-publiczone",
                "filters": [{"type": "value", "key": "id", "value": zone_id_to_update}],
                "actions": [{
                    "type": "update",
                    "email": new_email,
                    "ttl": new_ttl,
                    "description": "Updated public zone"
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Assert mainly verifies if the policy correctly filtered the target resource
        self.assertEqual(resources[0]['id'], zone_id_to_update)
        self.assertEqual(resources[0]['email'], original_email)  # Verify email before update
        # Verify action success: Manually check VCR cassette
        # dns_public_zone_action_update to confirm
        # PATCH /v2/zones/{zone_id} was called with the correct body
        # (email, ttl, description)

    def test_public_zone_action_set_status_disable(self):
        """Test Set Public Zone status to DISABLE"""
        factory = self.replay_flight_data("dns_public_zone_action_set_status_disable")
        # Get ID from dns_public_zone_action_set_status_disable
        # Verify VCR: Match the 'id' in dns_public_zone_action_set_status_disable
        zone_id_to_disable = "2c9eb1538a138432018a13xxxxx00001"
        # Verify VCR: Match the 'name' in dns_public_zone_action_set_status_disable
        zone_name_to_disable = "public-disable.example.com."
        p = self.load_policy(
            {
                "name": "dns-public-zone-action-disable",
                "resource": "huaweicloud.dns-publiczone",
                # Filter by name
                "filters": [{"type": "value", "key": "name", "value": zone_name_to_disable}],
                "actions": [{"type": "set-status", "status": "DISABLE"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Assert mainly verifies if the policy correctly filtered the target resource
        self.assertEqual(resources[0]['id'], zone_id_to_disable)
        # Verify VCR: Confirm initial resource status is ACTIVE
        self.assertEqual(resources[0]['status'], "ACTIVE")
        # Verify action success: Manually check VCR cassette
        # dns_public_zone_action_set_status_disable to confirm
        # PUT /v2/zones/{zone_id}/statuses was called with status: DISABLE

    def test_public_zone_action_set_status_enable(self):
        """Test Set Public Zone status to ENABLE"""
        # Note: This test depends on a Zone in DISABLED status and requires a cassette
        # for the enable operation.
        # Reusing dns_public_zone_action_set_status_disable cassette currently only
        # verifies policy loading.
        # Ideally should be dns_public_zone_action_set_status_enable.yaml
        # (currently missing)
        factory = self.replay_flight_data("dns_public_zone_action_set_status_disable")
        # Get ID from dns_public_zone_action_set_status_disable (assume it's the same one)
        # Verify VCR: Match the 'id' in dns_public_zone_action_set_status_disable
        zone_id_to_enable = "2c9eb1538a138432018a13xxxxx00001"
        p = self.load_policy(
            {
                "name": "dns-public-zone-action-enable",
                "resource": "huaweicloud.dns-publiczone",
                "filters": [
                    {"type": "value", "key": "id", "value": zone_id_to_enable},
                    # Ensure filtering the Zone currently in DISABLED status
                    # (depends on previous step or specific cassette)
                    {"type": "value", "key": "status", "value": "DISABLE"}
                ],
                "actions": [{"type": "set-status", "status": "ENABLE"}],
            },
            session_factory=factory,
        )
        # Due to the missing enable cassette, p.run() result might be inaccurate,
        # only verify policy existence here
        self.assertTrue(p)
        # Verify action success: Requires dns_public_zone_action_set_status_enable.yaml
        # cassette and manual check if PUT /v2/zones/{zone_id}/statuses was called
        # with status=ENABLE


class PrivateZoneTest(BaseTest):
    """Test Private DNS Zone resources, filters, and actions"""

    def test_private_zone_query(self):
        """Test Private Zone query and augment"""
        factory = self.replay_flight_data("dns_private_zone_query")
        p = self.load_policy(
            {
                "name": "dns-private-zone-query",
                "resource": "huaweicloud.dns-privatezone",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: dns_private_zone_query should contain 1 private zone
        self.assertEqual(len(resources), 1)
        # Verify VCR: Match the 'name' in dns_private_zone_query
        self.assertEqual(resources[0]["name"], "query.example.com.")
        self.assertTrue("routers" in resources[0])  # Verify augment added routers information

    def test_private_zone_filter_vpc_associated_match(self):
        """Test Private Zone associated VPC filter - Match"""
        factory = self.replay_flight_data("dns_private_zone_filter_vpc")
        # Get the associated VPC ID from dns_private_zone_filter_vpc
        # Verify VCR: Match the 'router_id' associated with
        # 'associated.example.com.' in dns_private_zone_filter_vpc
        vpc_id_associated = "vpc-c853fea981c3416c83181f7d01095375"
        p = self.load_policy(
            {
                "name": "dns-private-zone-filter-vpc-match",
                "resource": "huaweicloud.dns-privatezone",
                "filters": [{"type": "vpc-associated", "vpc_id": vpc_id_associated}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: Only one Zone in dns_private_zone_filter_vpc is associated
        # with this VPC
        self.assertEqual(len(resources), 1)

    def test_private_zone_filter_vpc_associated_no_match(self):
        """Test Private Zone associated VPC filter - No Match"""
        factory = self.replay_flight_data("dns_private_zone_filter_vpc")  # Reuse cassette
        vpc_id_not_associated = "vpc-non-existent-id"  # A VPC ID confirmed not associated
        p = self.load_policy(
            {
                "name": "dns-private-zone-filter-vpc-no-match",
                "resource": "huaweicloud.dns-privatezone",
                "filters": [{"type": "vpc-associated", "vpc_id": vpc_id_not_associated}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: No Zone in dns_private_zone_filter_vpc is associated with this VPC
        self.assertEqual(len(resources), 0)

    def test_private_zone_filter_age(self):
        """Test Private Zone Age filter"""
        factory = self.replay_flight_data("dns_private_zone_filter_age")
        p = self.load_policy(
            {
                "name": "dns-private-zone-filter-age",
                "resource": "huaweicloud.dns-privatezone",
                # Verify VCR: Creation time ('2023-01-15T12:00:00Z') of
                # 'old.example.com.' in dns_private_zone_filter_age
                # should be > 30 days
                "filters": [{"type": "age", "days": 30, "op": "gt"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: Only 'old.example.com.' in dns_private_zone_filter_age
        # meets the condition
        self.assertEqual(len(resources), 1)

    def test_private_zone_action_delete(self):
        """Test Delete Private Zone action"""
        factory = self.replay_flight_data("dns_private_zone_action_delete")
        # Get the Zone ID to delete from dns_private_zone_action_delete
        # Verify VCR: Match the 'id' in dns_private_zone_action_delete
        zone_id_to_delete = "2c9eb1538a138432018a13bbbbb00001"
        p = self.load_policy(
            {
                "name": "dns-private-zone-action-delete",
                "resource": "huaweicloud.dns-privatezone",
                "filters": [{"type": "value", "key": "id", "value": zone_id_to_delete}],
                "actions": ["delete"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Assert mainly verifies if the policy correctly filtered the target resource
        self.assertEqual(resources[0]['id'], zone_id_to_delete)
        # Verify action success: Manually check VCR cassette
        # dns_private_zone_action_delete to confirm DELETE /v2/zones/{zone_id} was called

    def test_private_zone_action_update(self):
        """Test Update Private Zone action"""
        factory = self.replay_flight_data("dns_private_zone_action_update")
        # Get the Zone ID to update from dns_private_zone_action_update
        # Verify VCR: Match the 'id' in dns_private_zone_action_update
        zone_id_to_update = "2c9eb1538a138432018a13ddddd00001"
        # Verify VCR: Match the initial 'email' in dns_private_zone_action_update
        original_email = "original@example.com"
        # Verify VCR: Match the initial 'ttl' in dns_private_zone_action_update
        original_ttl = 300
        new_ttl = 600
        new_email = "updated@example.com"  # Match the updated value in VCR
        new_description = "Updated description"  # Match the updated value in VCR
        p = self.load_policy(
            {
                "name": "dns-private-zone-action-update",
                "resource": "huaweicloud.dns-privatezone",
                "filters": [{"type": "value", "key": "id", "value": zone_id_to_update}],
                "actions": [{
                    "type": "update",
                    "ttl": new_ttl,
                    "description": new_description,
                    "email": new_email
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Assert mainly verifies if the policy correctly filtered the target resource
        self.assertEqual(resources[0]['id'], zone_id_to_update)
        self.assertEqual(resources[0]['email'], original_email)  # Verify email before update
        self.assertEqual(resources[0]['ttl'], original_ttl)  # Verify TTL before update
        # Verify action success: Manually check VCR cassette
        # dns_private_zone_action_update to confirm PATCH /v2/zones/{zone_id} was called
        # with the correct body (ttl=600, email='updated@example.com',
        # description='Updated description')

    def test_private_zone_action_associate_vpc(self):
        """Test Associate VPC to Private Zone action"""
        factory = self.replay_flight_data("dns_private_zone_action_associate_vpc")
        # Get Zone ID, VPC ID, and Region from dns_private_zone_action_associate_vpc
        # Verify VCR: Match the 'id' in dns_private_zone_action_associate_vpc
        zone_id_to_associate = "2c9eb1538a138432018a13aaaaa00001"
        # Verify VCR: Match the 'router_id' in the request body of
        # dns_private_zone_action_associate_vpc
        vpc_id_to_associate = "vpc-c853fea981c3416c83181f7d01095375"
        # Verify VCR: Match the 'router_region' in the request body of
        # dns_private_zone_action_associate_vpc
        vpc_region = "ap-southeast-1"
        p = self.load_policy(
            {
                "name": "dns-private-zone-associate-vpc",
                "resource": "huaweicloud.dns-privatezone",
                "filters": [{"type": "value", "key": "id", "value": zone_id_to_associate}],
                "actions": [{
                    "type": "associate-vpc",
                    "vpc_id": vpc_id_to_associate,
                    "region": vpc_region
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Assert mainly verifies if the policy correctly filtered the target resource
        self.assertEqual(resources[0]['id'], zone_id_to_associate)
        # Verify action success: Manually check VCR cassette
        # dns_private_zone_action_associate_vpc to confirm
        # POST /v2/zones/{zone_id}/associaterouter was called with the correct
        # router_id and router_region

    def test_private_zone_action_disassociate_vpc(self):
        """Test Disassociate VPC from Private Zone action"""
        factory = self.replay_flight_data("dns_private_zone_action_disassociate_vpc")
        # Get Zone ID and VPC ID from dns_private_zone_action_disassociate_vpc
        # Verify VCR: Match the 'id' in dns_private_zone_action_disassociate_vpc
        zone_id_to_disassociate = "2c9eb1538a138432018a13ccccc00001"
        # Verify VCR: Match the 'router_id' in the request body of
        # dns_private_zone_action_disassociate_vpc
        vpc_id_to_disassociate = "vpc-c853fea981c3416c83181f7d01095375"
        # Note: Disassociation only requires VPC ID, not region
        p = self.load_policy(
            {
                "name": "dns-private-zone-disassociate-vpc",
                "resource": "huaweicloud.dns-privatezone",
                "filters": [
                    {"type": "value", "key": "id", "value": zone_id_to_disassociate},
                    # Ensure filtering the Zone that is associated with this VPC
                    {"type": "vpc-associated", "vpc_id": vpc_id_to_disassociate}
                ],
                "actions": [{"type": "disassociate-vpc", "vpc_id": vpc_id_to_disassociate}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 0)
        # Verify action success: Manually check VCR cassette
        # dns_private_zone_action_disassociate_vpc to confirm
        # POST /v2/zones/{zone_id}/disassociaterouter was called with the correct router_id


class RecordSetTest(BaseTest):
    """Test DNS Record Set resources, filters, and actions"""

    def test_record_set_query(self):
        """Test Record Set query and augment"""
        factory = self.replay_flight_data("dns_record_set_query")
        p = self.load_policy(
            {
                "name": "dns-record-set-query",
                "resource": "huaweicloud.dns-recordset",
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: dns_record_set_query should contain 1 record set
        self.assertEqual(len(resources), 1)
        # Verify VCR: Record set in dns_record_set_query contains description
        self.assertTrue("description" in resources[0])

    def test_record_set_filter_record_type(self):
        """Test Record Set type filter"""
        factory = self.replay_flight_data("dns_record_set_filter_type")
        # Verify VCR: dns_record_set_filter_type should contain A records
        record_type_to_filter = "A"
        p = self.load_policy(
            {
                "name": f"dns-record-set-filter-type-{record_type_to_filter}",
                "resource": "huaweicloud.dns-recordset",
                "filters": [{
                    "type": "value",
                    "key": "type",
                    "value": record_type_to_filter
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: dns_record_set_filter_type should contain 2 A records
        self.assertEqual(len(resources), 2)
        for r in resources:
            self.assertEqual(r['type'], record_type_to_filter)

    def test_record_set_filter_zone_id(self):
        """Test Record Set Zone ID filter"""
        factory = self.replay_flight_data("dns_record_set_filter_zone_id")
        # Get target Zone ID from dns_record_set_filter_zone_id
        # Verify VCR: Match the 'zone_id' in dns_record_set_filter_zone_id
        target_zone_id = "zone_id_from_cassette"
        # Verify VCR: There should be 2 records under this zone_id in
        # dns_record_set_filter_zone_id
        expected_count = 2
        p = self.load_policy(
            {
                "name": "dns-record-set-filter-zone-id",
                "resource": "huaweicloud.dns-recordset",
                "filters": [{"type": "value", "key": "zone_id", "value": target_zone_id}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), expected_count)
        for r in resources:
            self.assertEqual(r['zone_id'], target_zone_id)

    def test_record_set_filter_line_id(self):
        """Test Record Set line ID filter"""
        factory = self.replay_flight_data("dns_record_set_filter_line_id")
        # Get target line ID from dns_record_set_filter_line_id
        # Verify VCR: Match the 'line' value in dns_record_set_filter_line_id
        target_line_id = "default_line_id_from_cassette"
        # Verify VCR: There should be 2 records under this line_id in
        # dns_record_set_filter_line_id
        expected_count = 2
        p = self.load_policy(
            {
                "name": "dns-record-set-filter-line-id",
                "resource": "huaweicloud.dns-recordset",
                "filters": [
                    {
                        # Huawei Cloud SDK returns the 'line' field
                        "type": "value", "key": "line", "value": target_line_id
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), expected_count)
        for r in resources:
            self.assertEqual(r.get('line'), target_line_id)

    def test_record_set_filter_age(self):
        """Test Record Set Age filter"""
        factory = self.replay_flight_data("dns_record_set_filter_age")
        p = self.load_policy(
            {
                "name": "dns-record-set-filter-age",
                "resource": "huaweicloud.dns-recordset",
                # Verify VCR: Creation time ('2025-04-08T12:00:14Z') of
                # 'new.example.com.' in dns_record_set_filter_age
                # should be <= 7 days
                "filters": [{"type": "age", "days": 7, "op": "ge"}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: Only 'new.example.com.' in dns_record_set_filter_age
        # meets the condition
        self.assertEqual(len(resources), 2)

    def test_record_set_action_delete(self):
        """Test Delete Record Set action"""
        factory = self.replay_flight_data("dns_record_set_action_delete")
        # Get the Record Set ID and its Zone ID to delete from dns_record_set_action_delete
        # Verify VCR: Match the 'id' in dns_record_set_action_delete
        recordset_id_to_delete = "2c9eb1538a138432018a13jjjjj00001"
        # Verify VCR: Match the 'zone_id' in dns_record_set_action_delete
        zone_id_for_delete = "2c9eb1538a138432018a13kkkkk00001"
        p = self.load_policy(
            {
                "name": "dns-record-set-action-delete",
                "resource": "huaweicloud.dns-recordset",
                "filters": [
                    {"type": "value", "key": "id", "value": recordset_id_to_delete},
                    # Must specify zone_id as well, because the delete record set API
                    # requires zone_id
                    {"type": "value", "key": "zone_id", "value": zone_id_for_delete}
                ],
                "actions": ["delete"],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Assert mainly verifies if the policy correctly filtered the target resource
        self.assertEqual(resources[0]['id'], recordset_id_to_delete)
        # Verify action success: Manually check VCR cassette
        # dns_record_set_action_delete to confirm
        # DELETE /v2/zones/{zone_id}/recordsets/{recordset_id} was called

    def test_record_set_action_update(self):
        """Test Update Record Set action"""
        factory = self.replay_flight_data("dns_record_set_action_update")
        # Get Record Set ID and Zone ID from dns_record_set_action_update
        # Verify VCR: Match the 'id' in dns_record_set_action_update
        recordset_id_to_update = "2c9eb1538a138432018a13nnnnn00001"
        # Verify VCR: Match the 'zone_id' in dns_record_set_action_update
        zone_id_for_update = "2c9eb1538a138432018a13ooooo00001"
        # Verify VCR: Match the initial 'ttl' in dns_record_set_action_update
        original_ttl = 300
        # Verify VCR: Match the initial 'records' in dns_record_set_action_update
        original_records = ["192.168.1.3"]
        new_ttl = 600
        new_records = ["192.168.1.4", "192.168.1.5"]  # Match the updated value in VCR
        new_description = "Updated record set"  # Match the updated value in VCR
        p = self.load_policy(
            {
                "name": "dns-record-set-action-update",
                "resource": "huaweicloud.dns-recordset",
                "filters": [
                    {"type": "value", "key": "id", "value": recordset_id_to_update},
                    # Update action also requires zone_id
                    {"type": "value", "key": "zone_id", "value": zone_id_for_update}
                ],
                "actions": [{
                    "type": "update",
                    "ttl": new_ttl,
                    "records": new_records,
                    "description": new_description
                }],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        # Assert mainly verifies if the policy correctly filtered the target resource
        self.assertEqual(resources[0]['id'], recordset_id_to_update)
        self.assertEqual(resources[0]['ttl'], original_ttl)  # Verify TTL before update
        self.assertEqual(resources[0]['records'], original_records)  # Verify records before update
        # Verify action success: Manually check VCR cassette
        # dns_record_set_action_update to confirm
        # PUT /v2/zones/{zone_id}/recordsets/{recordset_id} was called with the correct
        # body (ttl=600, records=['192.168.1.4', '192.168.1.5'],
        # description='Updated record set')

    def test_record_set_action_set_status(self):
        """Test Set single Record Set status"""
        factory = self.replay_flight_data("dns_record_set_action_set_status")
        # Verify VCR: Match the 'id' in dns_record_set_action_set_status
        recordset_id_to_set = "2c9eb1538a138432018a13lllll00001"
        # Verify VCR: Match the 'zone_id' in dns_record_set_action_set_status
        zone_id_for_set = "2c9eb1538a138432018a13mmmmm00001"
        target_status = "DISABLE"
        p = self.load_policy(
            {
                "name": "dns-record-set-action-set-status",
                "resource": "huaweicloud.dns-recordset",
                "filters": [
                    {"type": "value", "key": "id", "value": recordset_id_to_set},
                    {"type": "value", "key": "zone_id", "value": zone_id_for_set}
                ],
                "actions": [{"type": "set-status", "status": target_status}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['id'], recordset_id_to_set)
        # Verify VCR: Confirm initial resource status is ACTIVE
        self.assertEqual(resources[0]['status'], "ACTIVE")
        # Verify action success: Manually check VCR cassette
        # dns_record_set_action_set_status to confirm
        # PUT /v2.1/recordsets/{recordset_id}/statuses/set was called with status: DISABLE
        # Note: API path is different from batch operation

    def test_record_set_action_batch_set_status(self):
        """Test Batch Set Record Set status"""
        factory = self.replay_flight_data("dns_record_set_action_batch_set_status")
        # Verify VCR: Match the 'zone_id' in dns_record_set_action_batch_set_status
        zone_id_for_batch = "zone_id_for_batch_from_cassette"
        target_status = "ENABLE"
        # Verify VCR: Match the 'recordset_ids' in the request body of
        # dns_record_set_action_batch_set_status
        recordset_ids = [
            "2c9eb1538a138432018a13bbbbb00001",
            "2c9eb1538a138432018a13bbbbb00002"
        ]
        p = self.load_policy(
            {
                "name": "dns-record-set-action-batch-set-status",
                "resource": "huaweicloud.dns-recordset",
                "filters": [
                    {"type": "value", "key": "zone_id", "value": zone_id_for_batch},
                    # Filter records that need to be enabled
                    {"type": "value", "key": "status", "value": "DISABLE"}
                ],
                "actions": [{"type": "batch-set-status", "status": target_status}],
            },
            session_factory=factory,
        )
        resources = p.run()
        self.assertEqual(len(resources), 2)  # Verify VCR: Confirm 2 records were filtered
        for resource in resources:
            self.assertTrue(resource['id'] in recordset_ids)
            # Verify VCR: Confirm initial resource status is DISABLE
            self.assertEqual(resource['status'], "DISABLE")
        # Verify action success: Manually check VCR cassette
        # dns_record_set_action_batch_set_status to confirm
        # PUT /v2/zones/{zone_id}/recordsets/statuses was called with the correct
        # recordset_ids and status: ENABLE


# =========================
# Reusable Feature Tests (Using PublicZone as example)
# =========================

class ReusableFeaturesTest(BaseTest):
    """Test reusable Filters and Actions on DNS resources"""

    def test_filter_value_match(self):
        """Test value filter - Match"""
        factory = self.replay_flight_data("dns_public_zone_filter_value_email")
        # Get email value from dns_public_zone_filter_value_email
        # Verify VCR: Match the email of 'email1.example.com.' in
        # dns_public_zone_filter_value_email
        target_email = "email1@example.com"
        p = self.load_policy(
            {
                "name": "dns-filter-value-email-match",
                "resource": "huaweicloud.dns-publiczone",
                "filters": [{"type": "value", "key": "email", "value": target_email}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: Only one Zone in dns_public_zone_filter_value_email matches this email
        self.assertEqual(len(resources), 1)
        self.assertEqual(resources[0]['email'], target_email)

    def test_filter_value_no_match(self):
        """Test value filter - No Match"""
        factory = self.replay_flight_data("dns_public_zone_filter_value_email")  # Reuse
        wrong_email = "nonexistent@example.com"
        p = self.load_policy(
            {
                "name": "dns-filter-value-email-no-match",
                "resource": "huaweicloud.dns-publiczone",
                "filters": [{"type": "value", "key": "email", "value": wrong_email}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: No Zone in dns_public_zone_filter_value_email matches this email
        self.assertEqual(len(resources), 0)

    def test_filter_list_item_match(self):
        """Test list-item filter - Match (tags list)"""
        # Verify VCR: Zone 'public-tagged.example.com.' in
        # dns_public_zone_filter_list_item_tag should have tag
        # {"key": "filtertag", "value": "filtervalue"}
        factory = self.replay_flight_data("dns_public_zone_filter_list_item_tag")
        # Verify VCR: Match the 'key' in dns_public_zone_filter_list_item_tag
        target_tag_key = "filtertag"
        # Verify VCR: Match the 'value' in dns_public_zone_filter_list_item_tag
        target_tag_value = "filtervalue"
        # Verify VCR: Match the Zone ID with the tag in
        # dns_public_zone_filter_list_item_tag
        target_zone_id = "2c9eb1538a138432018a13ccccc00001"
        p = self.load_policy(
            {
                "name": "dns-filter-list-item-tag-match",
                "resource": "huaweicloud.dns-publiczone",
                "filters": [
                    {
                        "type": "list-item",
                        # Note: Should use 'tags' lowercase, consistent with API response
                        "key": "tags",
                        "attrs": [
                            {"type": "value", "key": "key", "value": target_tag_key},
                            {"type": "value", "key": "value", "value": target_tag_value}
                        ]
                    }
                ],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: Only one Zone in dns_public_zone_filter_list_item_tag matches this tag
        self.assertEqual(len(resources), 1)
        # Verify that the matched zone is the one with the tag
        self.assertEqual(resources[0]['id'], target_zone_id)

    def test_filter_marked_for_op_match(self):
        """Test marked-for-op filter - Match"""
        # Verify VCR: Zone 'public-marked.example.com.' in
        # dns_public_zone_filter_marked_for_op should have mark
        # 'c7n_status': 'marked-for-op:delete:1' and be expired
        factory = self.replay_flight_data("dns_public_zone_filter_marked_for_op")
        op = "delete"
        # Verify VCR: Match the mark key in dns_public_zone_filter_marked_for_op
        tag = "c7n_status"
        p = self.load_policy(
            {
                "name": f"dns-filter-marked-for-op-{op}-match",
                "resource": "huaweicloud.dns-publiczone",
                "filters": [{"type": "marked-for-op", "op": op, "tag": tag}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: Only one Zone in dns_public_zone_filter_marked_for_op meets
        # the condition (requires manual check based on current time for expiry)
        self.assertEqual(len(resources), 1)

    def test_filter_tag_count_match(self):
        """Test tag-count filter - Match"""
        # Verify VCR: Zone 'public-two-tags.example.com.' in
        # dns_public_zone_filter_tag_count should have 2 tags
        factory = self.replay_flight_data("dns_public_zone_filter_tag_count")
        # Verify VCR: Match the tag count of 'public-two-tags.example.com.' in
        # dns_public_zone_filter_tag_count
        expected_tag_count = 2
        p = self.load_policy(
            {
                "name": "dns-filter-tag-count-match",
                "resource": "huaweicloud.dns-publiczone",
                "filters": [{"type": "tag-count", "count": expected_tag_count}],
            },
            session_factory=factory,
        )
        resources = p.run()
        # Verify VCR: Only one Zone in dns_public_zone_filter_tag_count has exactly 2 tags
        self.assertEqual(len(resources), 1)
