# CSS314 parallel computing laboratory

Real measurements on an Apple M4 (10 physical cores: 4 performance and 6 efficiency; 128-byte cache lines), using student salt **30103059**, give N=1536 and M=768. Stride latency rose from **0.636 ns/element at stride 1** to **2.877 ns/element at stride 16**, consistent with poorer cache-line utilization. Interchanging the dense multiplication loops improved median runtime by **4.97x**, with both outputs agreeing within 1e-12. At eight workers, unpadded counters took **15.56 ms**, versus **12.60 ms** with native 128-byte padding; all 48 counter samples produced exact counts. Recovery was partial, and scheduling/short measurement intervals remain confounders. Strong stencil scaling peaked at **1.39x with four workers**; ten-worker efficiency was **13.71%**, compared with **23.98%** in weak scaling. The effective Amdahl fit gives s=0.666 and an idealized 1.50x ceiling. The stencil's optimistic arithmetic intensity is **0.3125 FLOP/byte**; [Apple's published 120 GB/s memory upper bound](https://support.apple.com/en-au/122209) implies a 37.5 GFLOP/s streaming ceiling. Missing FP64 compute peaks and hardware counters prevent a definitive Roofline classification. Raw samples, exact lossless numerical arrays, and independently recomputed checks are included.

- [Start here: explanation and run instructions](GUIDE.md)
- [Handout inconsistencies, AI restriction, and verification limits](HANDOUT_NOTES.md)
- [Raw measurements and local verification receipt](results/)

The instructor's verifier was not supplied. `verify_outputs.py` is an explicitly local, unsigned self-check. This repository is AI-assisted and does not satisfy the handout's ban on AI-generated code unless the instructor permits an exception.
