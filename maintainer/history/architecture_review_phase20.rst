Phase 20: architecture and correctness review
=============================================

This phase limits changes to high-confidence worker robustness improvements.
The complete Django and PostgreSQL regression gate is reserved for Phase 22.

Changes
-------

* Retry configuration validation and capped exponential backoff are now
  shared by outbox, external delivery and email digest workers. Public worker
  settings, retry budgets, statuses and command interfaces remain unchanged.
* A claim no longer performs an unbounded UPDATE against every previously
  abandoned, retry-exhausted record. Outbox and individual delivery queues
  transition at most 500 due exhausted rows per worker claim to FAILED.
* Each short transaction first selects a bounded set of IDs, then rechecks
  readiness and the retry count before writing a terminal state. A worker
  that has renewed a lease since the initial selection is not overwritten.
* A healthy due job can still be claimed in the same pass. Subsequent worker
  passes reconcile the remainder of a larger exhausted backlog.

Architectural boundaries retained
---------------------------------

* QuerySet methods build selections; the lifecycle service mutates state.
* Event intent is stored atomically in the optional outbox; external receivers
  execute outside the mutation transaction.
* Delivery jobs own provider-specific retries independently of outbox retries.
* Django Channels, Redis, Celery and external providers remain optional.
* Current dynamic and snapshot group audiences, independent read-state and
  notification preferences remain unchanged.

Known integration gates
-----------------------

* Exercise concurrent claims on PostgreSQL, including stale lease recovery,
  interleaving worker acknowledgements and retry/requeue races.
* Verify all migrations from a fresh database and from the released schema.
* Check complete Django/DRF permission and serializer behavior in one test run.
* Run both delivery worker and digest scheduler tests across time zones.
* Check compatibility of old GET actions and the retained queryset facade.
* The final hardening pass resolved bulk mark-as-sent fan-out by emitting
  individual IDs alongside the legacy aggregate. Direct ORM writes do not
  automatically emit lifecycle events; providers still use at-least-once
  delivery and require their own idempotency handling.

Source/static checks are not a substitute for those deferred runtime gates.
