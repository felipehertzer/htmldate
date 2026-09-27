Explicit timestamps
===================

This htmldate fork also supports ``find_date(..., preserve_timestamp=True)``. It preserves an explicit
ISO publication timestamp (including its offset and fractional seconds) from
page metadata or JSON-LD belonging to the current article. If none is available,
normal htmldate extraction applies. Date-only values remain date-only, and naive
timestamps remain naive. Set ``original_date=False`` to request modification
timestamps instead. This option takes precedence over ``outputformat`` only when
an explicit timestamp is found; the default date-only API remains unchanged.

