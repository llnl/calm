# Transitional public API surface

<!-- transitional-public-api-decision-table:begin -->
| Import path | Decision | Modern alternative | Exit criteria |

| calm.Slab | keep-temporary | calm.slab.Slab | remove-after-call-site-audit |
| calm.SlabSpec | keep-temporary | calm.slab.SlabSpec | remove-after-call-site-audit |
| calm.slab.Slab | keep-temporary | calm.slab.Slab | remove-after-call-site-audit |
| calm.slab.SlabSpec | keep-temporary | calm.slab.SlabSpec | remove-after-call-site-audit |
<!-- transitional-public-api-decision-table:end -->

This document records public API transition decisions in a machine-readable
table marked by the begin/end markers used by guardrail tests.
