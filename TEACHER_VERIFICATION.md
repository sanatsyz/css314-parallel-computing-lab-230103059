# Teacher verification on this Mac

The uploaded `verify_outputs.py.txt` is preserved unchanged and copied byte for byte to `verify_outputs.py`. Its SHA-256 is `bce8d586fd800f888d5001cb6919fd915590f9ec25dab1ab62bd703a502ebb21`. The CS482 strings in that supplied source have been retained; the course is CSS314.

Run the teacher check and then the separate numerical verification:

```bash
.venv/bin/python check_teacher.py
.venv/bin/python verify_numerics.py --student-id 30103059
```

`check_teacher.py` first verifies the supplied script's bytes, copies the seven required metadata files to a temporary directory, and runs the unchanged teacher script there. It records the full result and separate milestone diagnostics in `results/teacher_verification.json` and `results/teacher_verification.log`. These diagnostic calls do not turn a failed full run into a pass. Running `.venv/bin/python verify_outputs.py` directly checks the same files from the repository directory and stops at the same first failure.

## Actual outcome

| Check | Outcome | Explanation |
| --- | --- | --- |
| Full teacher script | Fails with exit status 1 | Stops at M0's fixed 64-byte cache-line requirement. |
| M0: topology and salt | Fails | The operating system reports 128-byte lines on this Apple M4; the script requires exactly 64. The student ID and salted N remain correct. |
| M1: locality and loop order | Passes independently | Measured stride and matrix timings are exposed under the teacher's expected field names. |
| M2: false sharing | Passes independently | Actual Karp-Flatt values now appear in the expected columns, with padding variants identified explicitly. |
| M3: scaling and Roofline | Fails independently | The script requires a definitive memory-bound or compute-bound label. The available data does not establish one because the FP64 compute peak and actual DRAM traffic are unknown. |
| Independent numerical verification | Passes | Saved matrix products, all counter results, stencil outputs, digests, and recomputed metrics match their references. |

The full teacher script has not passed, and no teacher `verification_receipt.sig` has been generated. The former unsigned local receipt has moved to `results/local_verification_receipt.json`, so it cannot be mistaken for the teacher's output. Only a successful run of the unchanged supplied script can produce the teacher receipt through the runner.

## Compatible fields added to real results

No benchmark timings or hardware readings were changed. Existing fields are retained alongside these aliases:

| File | Additional fields |
| --- | --- |
| `stride_results.tsv` | `stride = stride_elements`; `latency_ns = ns_per_element`. |
| `loop_interchange.json` | `naive_time_s` and `interchanged_time_s`, converting the existing median nanoseconds to seconds. |
| `false_sharing_karp_flatt.tsv` | `p`, `e_unpadded`, `e_padded`, `e_padded_128`, `e_privatized`, and explicit padding-variant labels. |
| `roofline_summary.json` | `arithmetic_intensity = 5/16`; `classification = "undetermined"`. |

The false-sharing table retains one row per variant and worker count. The compatibility columns repeat that worker count's cross-variant metrics on each corresponding row. `e_padded` uses the handout's literal 64-byte spacing (`padded_64` on this Mac), while `e_padded_128` identifies the hardware-aware 128-byte result. These are the handout-requested Karp-Flatt calculations on a workload that grows with the worker count, not fixed-work serial fractions.

The teacher script checks table structure and trends but does not load or compare the saved numerical arrays. Its receipt token is a SHA-256 hash of a public fixed string, student ID, and N; it is not an authenticated digital signature. `verify_numerics.py` retains the stronger output checks independently.

## Clarification needed from the teacher

The concrete issue to raise is: "My Apple M4 reports 128-byte cache lines, but the supplied verifier requires exactly 64. May the checker accept the detected cache-line size, and how should the Roofline result be classified when a documented FP64 CPU peak is unavailable?"

The repository preserves the real measurements and the original checks while awaiting that clarification.
