{% for src_path, stats in src_stats|dictsort %}
{% if stats.snippets_markdown %}

## {{ src_path | replace(".", "&#46;") }}
{% for snippet in stats.snippets_markdown %}

{{ snippet }}

---

{% endfor %}

{% endif %}
{% endfor %}
