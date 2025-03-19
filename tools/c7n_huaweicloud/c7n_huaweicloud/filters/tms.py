from c7n import utils
from c7n.filters import OPERATORS, Filter


def register_tms_filters(filters):
    filters.register('tag-count', TagCountFilter)

class TagCountFilter(Filter):
    """Simplify tag counting..

    ie. these two blocks are equivalent

    .. code-block :: yaml

       - filters:
           - type: value
             op: gte
             count: 5

       - filters:
           - type: tag-count
             count: 5
    """
    schema = utils.type_schema(
        'tag-count',
        count={'type': 'integer', 'minimum': 0},
        op={'enum': list(OPERATORS.keys())})
    schema_alias = True

    def __call__(self, i):
        count = self.data.get('count', 5)
        op_name = self.data.get('op', 'gte')
        op = OPERATORS.get(op_name)
        tag_count = len([t for t in i.get('tags', {}) if not t.startswith('_sys')])
        return op(tag_count, count)