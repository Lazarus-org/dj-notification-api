dj-notification-api
===================

Build a personal notification inbox in Django, then add email, webhooks or
real-time updates when your application needs them. Each recipient has their
own read and cleared state, even when several people share one notification.

Start with :doc:`quick_start` to create a notification and follow it from the
unread inbox into the activity list. The core inbox needs no worker, Redis,
Channels or provider account.

Choose your integration
-----------------------

.. list-table::
   :header-rows: 1
   :widths: 25 45 30

   * - You need
     - Configure
     - Read
   * - An in-app inbox
     - Django app, migrations and authenticated REST routes
     - :doc:`quick_start`, :doc:`api_guide`
   * - Email or another external channel
     - Outbox, delivery receiver, backend and two workers
     - :doc:`delivery`
   * - Live inbox refreshes
     - Channels adapter, authenticated ASGI routing and channel layer
     - :doc:`channels`
   * - Daily or weekly email summaries
     - Email delivery and per-user schedules
     - :doc:`schedules_and_digests`
   * - Failure diagnosis and replay
     - Management commands and process monitoring
     - :doc:`operations`, :doc:`troubleshooting`

Learn and integrate
-------------------

.. toctree::
   :maxdepth: 2

   Overview <self>
   quick_start
   concepts
   usage
   api_guide
   settings
   customization
   roles

Deliver and notify in real time
-------------------------------

.. toctree::
   :maxdepth: 2

   delivery
   templates_and_channels
   schedules_and_digests
   routing_rules
   events
   outbox
   channels

Run in production
------------------

.. toctree::
   :maxdepth: 2

   operations
   troubleshooting
   delivery_analytics
   upgrading

Contribute
-----------

.. toctree::
   :maxdepth: 1

   development_toolchain
   contributing

Project links
--------------

* `Source and issues <https://github.com/lazarus-org/dj-notification-api>`_
* `PyPI package <https://pypi.org/project/dj-notification-api/>`_
* `Changelog <https://github.com/lazarus-org/dj-notification-api/blob/main/CHANGELOG.md>`_

Use documentation matching your installed release. Read :doc:`upgrading`
before adopting changed framework requirements or HTTP behavior.
