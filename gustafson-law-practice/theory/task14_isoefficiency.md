# Task 14 — Isoeﬃciency

Isoefficiency W(P) is the problem-size growth required to keep parallel efficiency fixed as processor count rises, accounting for algorithm overhead. In an ideal Gustafson-compliant program, each worker receives fixed work w₀, so `W(P)=P w₀`. If observed α stays constant, `E=1−α+α/P` tends to 1−α; linear work growth is sufficient for constant asymptotic efficiency.

This is a conditional derivation, not a universal isoefficiency result. If a global reduction adds O(log P) overhead while local work remains fixed, efficiency declines; local work may need to grow at least with log P, giving W(P)=Ω(P log P) under that simplified overhead model. The algorithm's overhead function, not Gustafson's law alone, determines isoefficiency.
