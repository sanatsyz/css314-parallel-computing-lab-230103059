# Run order
1. Do Phase 0 terminal commands; note Pphys, L1d, L2.
2. export STUDENT_ID=<id> PPHYS=<physical cores> L1D_KB=<kib> L2_KB=<kib>   (Windows: `set`)
3. python3 task0_cal.py; python3 task1_falsesharing.py; python3 task2_scaling.py;
   python3 task3_roofline_gemm.py; python3 task4_scheduling.py
   (close other apps, plug in power; full runs take ~10-30 min total)
4. python3 make_report.py <id>   -> lab_report_<id>.md
