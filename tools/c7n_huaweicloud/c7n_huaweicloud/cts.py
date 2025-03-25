# Copyright The Cloud Custodian Authors.
# SPDX-License-Identifier: Apache-2.0
from c7n.utils import jmespath_search, jmespath_compile


class CloudTraceServiceEvents:
    """A mapping of events to resource types"""

    trace_events = {
        'CreateFunction': {
            'source': 'FunctionGraph',
            'ids': 'resource_id',
        }
    }

    @classmethod
    def get(cls, event_name):
        return cls.trace_events.get(event_name)

    @classmethod
    def match(cls, event):
        if 'data' not in event:
            return False
        if 'trace_name' not in event['data']:
            return False
        k = event['data']['trace_name']

        if k in cls.trace_events:
            v = dict(cls.trace_events[k])
            if isinstance(v['ids'], str):
                v['ids'] = e = jmespath_compile('data.%s' % v['ids'])
                cls.trace_events[k]['ids'] = e
            return v

        return False

    @classmethod
    def get_trace_ids(cls, event, mode):
        """extract resources ids from a CTS event."""
        resource_ids = ()
        event_name = event['data']['trace_name']
        event_source = event['data']['service_type']
        for e in mode.get('events', []):
            if not isinstance(e, dict):
                # Check if we have a short cut / alias
                info = CloudTraceServiceEvents.match(event)
                if info:
                    return info['ids'].search(event)
                continue
            if event_name != e.get('event'):
                continue
            if event_source != e.get('source'):
                continue

            id_query = e.get('ids')
            if not id_query:
                raise ValueError("No id query configured")
            evt = event

            if not id_query.startswith('data.'):
                evt = event.get('data', {})
            resource_ids = jmespath_search(id_query, evt)
            if resource_ids:
                break
        return resource_ids

    @classmethod
    def get_ids(cls, event, mode):
        mode_type = mode.get('type')
        if mode_type == 'ec2-instance-state':
            resource_ids = [event.get('detail', {}).get('instance-id')]
        elif mode_type == 'asg-instance-state':
            resource_ids = [event.get('detail', {}).get('AutoScalingGroupName')]
        elif mode_type != 'cloudtrace':
            return None
        else:
            resource_ids = cls.get_trace_ids(event, mode)

        if not isinstance(resource_ids, (tuple, list)):
            resource_ids = [resource_ids]

        return list(filter(None, resource_ids))
