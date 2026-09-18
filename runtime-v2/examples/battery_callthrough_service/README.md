# Battery Call-Through Service — Runtime V2

This example demonstrates the Runtime V2 authority-bound native execution path using the same battery-service model as the minimal example.

The consequential `recharge` operation is a real registered Python callable. Registration is non-authorizing. The callable can be entered only after a canonical PV-PP decision produces an execution license, epsilon instantiates a current execution episode, and the runtime issues a single-use native execution authorization for the registered binding.

The example demonstrates four properties:

1. **Successful call-through:** canonical decision → execution license → epsilon episode → native authorization → registered charger callable → execution result → Layer-1 transition and validation.
2. **Fail-closed denial:** an authorization invalidated before callable entry cannot execute, and the charger call count remains zero.
3. **Replay resistance:** a consumed authorization cannot execute a second time.
4. **Error propagation:** callable failures return normalized Runtime V2 evidence. A clean failure asserts no external effect; an unclassified post-entry failure is conservatively `indeterminate` because absence of a successful return is not proof that no external effect occurred.

The native callable does **not** mutate PV-PP actual persistent state. Layer 1 remains the authoritative host mutation boundary.
