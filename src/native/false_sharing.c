/*
 * Deliberately perform every counter update in memory. Volatile prevents the
 * compiler from replacing the loop with a single += iterations operation.
 * Each process owns its counter, so neither atomics nor a global lock belong
 * in this hot loop. The shared array is read only after workers finish.
 */
#include <stdint.h>

void increment_shared(volatile int64_t *counter, int64_t iterations) {
    for (int64_t i = 0; i < iterations; ++i) {
        *counter += 1;
    }
}

/* The private stack counter has the same volatile load/add/store workload. */
int64_t increment_private(int64_t iterations) {
    volatile int64_t counter = 0;
    for (int64_t i = 0; i < iterations; ++i) {
        counter += 1;
    }
    return counter;
}
