You have an invalid Kodiak configuration file.

## configuration file
> config_file_expression: master:.kodiak.toml
> line count: 1

<pre>
version = 12
</pre>

## configuration error message
<pre>
# pretty 
1 validation error for V1
version
  Version must be `1` (type=value_error.invalidversion)


# json 
[
  {
    "loc": [
      "version"
    ],
    "msg": "Version must be `1`",
    "type": "value_error.invalidversion"
  }
]
</pre>

## notes
- Check the Kodiak docs for setup information at https://kodiakhq.com/docs/quickstart.
- A configuration reference is available at https://kodiakhq.com/docs/config-reference.
- Full examples are available at https://kodiakhq.com/docs/recipes


If you need help, you can open a GitHub issue, check the docs, or reach us privately at support@kodiakhq.com.

[docs](https://kodiakhq.com/docs/troubleshooting) | [dashboard](https://app.kodiakhq.com) | [support](https://kodiakhq.com/help)

