# kodiak.events

Here we store the minimal schema definitions we need to parse webhook payloads. To reduce the chance of parsing errors, we only parse what we need.

Some schema structures like `Repository` are duplicated between events. This ensures we only parse what we need for an individual event and out of concern that information for a `Repository` in one payload is not the same as another.
