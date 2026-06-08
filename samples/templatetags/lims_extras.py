from django import template

register = template.Library()

@register.simple_tag
def url_params(request, **kwargs):
    """Builds a query string from current GET params, overriding with kwargs."""
    params = request.GET.copy()
    for key, value in kwargs.items():
        if value is not None:
            params[key] = value
        elif key in params:
            del params[key]
    return params.urlencode()


@register.filter
def dash_if_none(value):
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