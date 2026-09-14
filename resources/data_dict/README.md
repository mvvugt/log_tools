# The `data_dict` directory

This directory should contain text tables that will be built into
`.rst` documentation, using the [`doc-column-list`](https://cfinan.gitlab.io/pyaddons/scripts/python_scripts.html#doc-column-list)
script in [`pyaddons`](https://cfinan.gitlab.io/pyaddons/index.html).

The data dictionary tables are turned into numbered lists that can be
added to ReST documentation. This requires the input file to be tab
delimited and have a header of:

1. `column` (`int`) - The column number.
2. `name` - (`str`) - The column name.
3. `data_type` (`str`) - The data type, such as `string` or `integer`.
   This has no set value, i.e. you can make up your own data types.
4. `data_type_length` (`int`) - An optional length of the data type,
   only used for strings.
5. `description` (`str`) - A long form description of the column. The
   order of the columns is not important. The description can contain
   restructured text markup.

`log_tools` has no tabular data schema to document yet -- this exists
so the convention is in place if/when one is added.
