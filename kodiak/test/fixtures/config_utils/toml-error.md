You have an invalid Kodiak configuration file.

## configuration file
> config_file_expression: master:.kodiak.toml
> line count: 1

<pre>
[[[ version = 12
</pre>

## configuration error message
<pre>
TomlDecodeError(&#39;Key group not on a line by itself. (line 1 column 1 char 0)&#39;)
</pre>

## notes
- Setup information can be found in the [Kodiak README](https://github.com/chdsbd/kodiak/blob/master/README.md)
- Example configuration files can be found in [kodiak/test/fixtures/config](https://github.com/chdsbd/kodiak/tree/master/kodiak/test/fixtures/config)
- The corresponding Python models can be found in [kodiak/config.py](https://github.com/chdsbd/kodiak/blob/master/kodiak/config.py)

If you need any help, please open an issue on https://github.com/chdsbd/kodiak.
