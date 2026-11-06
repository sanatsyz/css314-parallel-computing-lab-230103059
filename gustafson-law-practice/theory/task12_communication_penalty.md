# Task 12 — Communication penalty extension

Let α₀ represent serial work excluding communication and let C(P)≥0 be additional non-overlapped communication time relative to normalized baseline runtime. A direct model is `S_C(P)=[α₀+P(1−α₀)]/[1+C(P)]`. The numerator is the equivalent serial time for expanded work; the denominator is actual parallel elapsed time extended by communication. Example models include `C(P)=β log₂P` for a tree latency term or `C(P)=β√P` for a surface/traffic regime in a stated topology. Fit β from measurements; the growth law depends on network and decomposition.

If instead C(P) is expressed as a fraction of total normalized parallel elapsed time, include it in `α_eff(P)` and use `S=P−α_eff(P)(P−1)` only when the fractions are disjoint. Do not count communication both in C and α.
