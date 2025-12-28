from django import template

register = template.Library()

@register.filter
def get_item(dictionary, key):
    """Get an item from a dictionary in templates"""
    if dictionary:
        return dictionary.get(key)
    return None
