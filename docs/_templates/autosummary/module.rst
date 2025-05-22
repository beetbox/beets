{{ fullname | escape | underline}}
{% block modules %}
{% if modules %}
.. rubric:: Modules

{% for item in modules %}
{{ item }}

{%- endfor %}
{% endif %}
{% endblock %}