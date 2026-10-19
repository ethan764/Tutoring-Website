# Test suite

Run the application tests from the repository root:

```sh
python -m pytest -q
```

The suite uses Flask's test client and a fresh in-memory SQLite database for
each test. The app factory accepts a configuration override so tests do not
read or modify the development database.

Coverage includes registration, login, email verification, authorization,
student records and lesson history, lesson planning and recording, schedule
generation and synchronization, payments request handling, and rendered public
pages. Model/route tests replace integrations with test doubles before the
application imports its blueprints.

No live external service is contacted. Google Sheets reads/writes, SMTP email
delivery, Todoist task operations, Stripe API and webhook-signature handling,
and Ollama responses are represented by stubs or mocks. The tests verify
application behavior at those boundaries but cannot establish credentials,
network availability, live API compatibility, remote spreadsheet layout, or
the correctness of production webhook configuration.
