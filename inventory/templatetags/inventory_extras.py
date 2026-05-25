from django import template
register = template.Library()

@register.filter
def get_field(form, inventory_id):
    return form[f'qty_{inventory_id}']