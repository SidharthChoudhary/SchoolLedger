from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary in templates"""
    if dictionary:
        return dictionary.get(key)
    return None

@register.filter
def indian_number(value):
    """Format a number in Indian numbering style: e.g. 1234567 → 12,34,567"""
    try:
        value = int(round(float(value)))
    except (ValueError, TypeError):
        return value
    negative = value < 0
    value = abs(value)
    s = str(value)
    if len(s) <= 3:
        result = s
    else:
        last3 = s[-3:]
        rest = s[:-3]
        parts = []
        while len(rest) > 2:
            parts.append(rest[-2:])
            rest = rest[:-2]
        if rest:
            parts.append(rest)
        result = ','.join(reversed(parts)) + ',' + last3
    return '-' + result if negative else result
