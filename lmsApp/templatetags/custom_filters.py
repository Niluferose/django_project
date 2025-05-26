from django import template

register = template.Library()

@register.filter
def replace_stars(value):
    if value:
        return value.replace('**', '')
    return value