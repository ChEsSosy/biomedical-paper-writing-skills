# Article Polisher patch/application layer 0.1.4 patch record

Status: candidate; not frozen, installed, or activated.

Patch layer 0.1.4 is derived from preserved rejected candidate 0.1.3. It uses the core 0.1.4 authority-state consistency gate before applying an operation, so an M02 plan or claim map whose top-level author-approved label contradicts nested pending/open state fails closed before source text is modified. The same conditions are rechecked by the core validator after application.

No operation vocabulary, schema, scientific-content rule, frozen contract, or integration route changed.
