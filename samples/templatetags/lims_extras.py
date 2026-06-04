from django import template
from django.utils import timezone

register = template.Library()

@register.filter
def dash_if_none(value):
    """Returns — for any falsy value."""
    if value in (None, '', 0):
        return '—'
    return value

@register.filter
def lab_date(value):
    """Formats a date as: May 27, 2026"""
    if not value:
        return '—'
    if hasattr(value, 'strftime'):
        return value.strftime('%b %d, %Y').replace(' 0', ' ')
    return value