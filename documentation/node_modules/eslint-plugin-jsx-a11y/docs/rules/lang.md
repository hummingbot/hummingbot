# lang

The `lang` prop on the `<html>` element must be a valid IETF's BCP 47 language tag.

#### References

1. [axe-core, valid-lang](https://dequeuniversity.com/rules/axe/3.2/valid-lang)
2. [Language tags in HTML and XML](https://www.w3.org/International/articles/language-tags/)
3. [IANA Language Subtag Registry](https://www.iana.org/assignments/language-subtag-registry/language-subtag-registry)

## Rule details

This rule takes no arguments.

### Succeed

```jsx
<html lang="en">
<html lang="en-US">
```

### Fail

```jsx
<html>
<html lang="foo">
```
